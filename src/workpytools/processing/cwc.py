from __future__ import annotations

import argparse
import logging
import re
import unicodedata
from importlib import resources
from pathlib import Path

from wordcloud import STOPWORDS, WordCloud

from workpytools.common.clipboard import load_text
from workpytools.common.clustering import agglomerative_average_linkage
from workpytools.common.config import load_default_config
from workpytools.common.embedding import DEFAULT_MODEL_NAME, embed_sentences
from workpytools.common.output import describe_output, save_result
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_DEFAULT_FONT = Path(r"C:\Windows\Fonts\meiryo.ttc")

# 文字クラス内では ] と - をエスケープする（] は先頭以外だとクラスの終端と解釈される）。
_SPLIT_CHARS = "。（）「」『』【】〔〕［\\］｛｝〈〉《》()\\[\\]{}\\s"
_SPLIT_PATTERN = re.compile(f"[{_SPLIT_CHARS}]+")

# --similar 用の文分割。正規化後は全角!/?が半角になるため半角で指定する。
_SENTENCE_SPLIT_PATTERN = re.compile(r"[。!?\s]+")

# --similar の入力文数の上限。凝集型クラスタリングはO(n^2)の距離行列を使うため無制限にはしない。
_SIMILAR_MAX_SENTENCES = 2000

_HINSHI_CHOICES = (
    "名詞",
    "動詞",
    "形容詞",
    "副詞",
    "助詞",
    "助動詞",
    "連体詞",
    "接続詞",
    "感動詞",
    "接頭詞",
    "記号",
    "フィラー",
    "その他",
)

# 送り仮名・漢字かな交ぜ書きのゆれをNFKC正規化の後に統一する変換表。
_KANA_KANJI_REWRITES = {
    "無し": "なし",
    "有る": "ある",
    "無い": "ない",
}

_DEFAULT_STOPWORDS_JA = frozenset(
    {
        # 形式名詞・指示語
        "こと",
        "もの",
        "これ",
        "それ",
        "あれ",
        "ため",
        "よう",
        "とき",
        # 汎用動詞・補助的な語
        "する",
        "ある",
        "いる",
        "なる",
        "できる",
        # 助詞・助動詞
        "の",
        "に",
        "は",
        "を",
        "が",
        "で",
        "と",
        "も",
        "や",
        "から",
        "まで",
        "です",
        "ます",
    }
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    for old, new in _KANA_KANJI_REWRITES.items():
        normalized = normalized.replace(old, new)
    return normalized


def _split_default(text: str) -> list[str]:
    return [token for token in _SPLIT_PATTERN.split(text) if token]


def _split_wakachi(text: str, user_dict: Path | None) -> list[tuple[str, str, str]]:
    """Tokenize with Janome. Returns (surface, base_form, hinshi) triples."""
    from janome.tokenizer import Tokenizer  # 遅延インポート: -w/--hinshi指定時のみ読み込む

    if user_dict is not None:
        tokenizer = Tokenizer(udic=str(user_dict), udic_type="simpledic")
    else:
        tokenizer = Tokenizer()

    result = []
    for token in tokenizer.tokenize(text):
        hinshi = token.part_of_speech.split(",")[0]
        result.append((token.surface, token.base_form, hinshi))
    return result


def _resolve_user_dict(args: argparse.Namespace) -> Path | None:
    if getattr(args, "no_user_dict", False):
        return None

    # 同梱データ(workpytools.data)はpip installでもsite-packages配下に
    # 実ファイルとして展開される通常のwheel配布を前提にしている。
    # as_file()のwithブロックを抜けた後も返されたパスは有効（zipimport等の
    # 特殊なインストール形態は対象外）。
    candidate: Path | None = None
    with resources.as_file(resources.files("workpytools.data") / "user.dic") as bundled:
        if bundled.exists():
            candidate = bundled

    config = load_default_config()
    configured = config.get("cwc", {}).get("user_dict")
    if configured is not None:
        configured_path = Path(configured)
        if configured_path.exists():
            candidate = configured_path
        else:
            logger.warning(
                "設定ファイルのユーザー辞書が見つからないため無視します: %s", configured_path
            )

    if args.user_dict is not None:
        cli_path = Path(args.user_dict)
        if cli_path.exists():
            candidate = cli_path
        else:
            logger.warning("--user-dictで指定された辞書が見つかりません: %s", cli_path)

    return candidate


def _resolve_synonym_dict(args: argparse.Namespace) -> Path | None:
    if getattr(args, "no_synonym_dict", False):
        return None

    candidate: Path | None = None
    with resources.as_file(resources.files("workpytools.data") / "synonym.tsv") as bundled:
        if bundled.exists():
            candidate = bundled

    config = load_default_config()
    configured = config.get("cwc", {}).get("synonym_dict")
    if configured is not None:
        configured_path = Path(configured)
        if configured_path.exists():
            candidate = configured_path
        else:
            logger.warning(
                "設定ファイルの同義語辞書が見つからないため無視します: %s", configured_path
            )

    if args.synonym_dict is not None:
        cli_path = Path(args.synonym_dict)
        if cli_path.exists():
            candidate = cli_path
        else:
            logger.warning("--synonym-dictで指定された辞書が見つかりません: %s", cli_path)

    return candidate


def _load_synonym_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            columns = line.split("\t")
            representative, *variants = columns
            for variant in variants:
                mapping[variant] = representative
    return mapping


def _resolve_stopwords(args: argparse.Namespace) -> frozenset[str]:
    if args.no_default_stopwords:
        words: set[str] = set()
    else:
        words = set(_DEFAULT_STOPWORDS_JA) | set(STOPWORDS)

    if args.stopwords:
        for chunk in args.stopwords:
            words.update(w.strip() for w in chunk.split(",") if w.strip())

    if args.stopwords_file:
        path = Path(args.stopwords_file)
        with path.open("r", encoding="utf-8") as f:
            words.update(line.strip() for line in f if line.strip())

    return frozenset(words)


class CwcProcessor(Processor):
    """Generate a word cloud image from input text.

    Input source is auto-detected (file path or clipboard), following the
    same convention as touka/denoise/kukiri. Word splitting defaults to
    delimiter-based splitting; `-w` switches to Janome tokenization.
    """

    name = "cwc"
    help = "テキストからワードクラウド画像を生成する（ファイルパス／クリップボード入力対応）"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "path",
            nargs="?",
            default=None,
            help="テキストファイルパス。省略時はクリップボードのテキスト/コピーしたファイルを使用",
        )
        parser.add_argument(
            "-o", "--output", default=None, help="出力先パス（省略時は自動生成、拡張子はpng）"
        )
        parser.add_argument(
            "-e",
            "--encoding",
            default=None,
            help="入力ファイルのエンコーディングを明示指定（省略時はUTF-8→CP932の順に試す）",
        )
        parser.add_argument(
            "-w", "--wakachi", action="store_true", help="Janomeによる分かち書きで分割する"
        )
        parser.add_argument(
            "-i",
            "--hinshi",
            nargs="+",
            default=None,
            help=(
                "集計対象の品詞を指定（複数可、カンマ区切りも可）。"
                f"指定可能: {', '.join(_HINSHI_CHOICES)}"
            ),
        )
        parser.add_argument(
            "-s", "--semantic", action="store_true", help="同義語辞書で異表記を代表語に寄せる"
        )
        parser.add_argument(
            "-y", "--synonym-dict", default=None, help="同義語辞書ファイルのパス"
        )
        parser.add_argument(
            "-Y", "--no-synonym-dict", action="store_true", help="同義語辞書を一切使用しない"
        )
        parser.add_argument("-u", "--user-dict", default=None, help="Janomeユーザー辞書のパス")
        parser.add_argument(
            "-U",
            "--no-user-dict",
            action="store_true",
            help="Janomeユーザー辞書を一切使用しない",
        )
        parser.add_argument(
            "-x",
            "--stopwords",
            action="append",
            default=None,
            help="追加するストップワード（カンマ区切り）",
        )
        parser.add_argument(
            "-X",
            "--stopwords-file",
            default=None,
            help="追加するストップワードのファイルパス",
        )
        parser.add_argument(
            "-D",
            "--no-default-stopwords",
            action="store_true",
            help="デフォルトのストップワードを無効化する",
        )
        parser.add_argument(
            "-f", "--font", default=None, help="使用するフォントファイルのパス"
        )
        parser.add_argument(
            "-m",
            "--similar",
            action="store_true",
            help="集計単位を語ではなく文にし、埋め込みベクトルの類似度でクラスタリングする",
        )
        parser.add_argument(
            "-t",
            "--similar-threshold",
            type=float,
            default=0.2,
            help="--similar のクラスタをまとめる距離の閾値（コサイン距離、既定: 0.2）",
        )
        parser.add_argument(
            "-M",
            "--similar-model",
            default=DEFAULT_MODEL_NAME,
            help="--similar で使用する埋め込みモデル名",
        )
        parser.add_argument(
            "-l",
            "--similar-max-length",
            type=int,
            default=10,
            help="--similar の代表文の表示文字数の上限（0で無制限、既定: 10）",
        )

    def run(self, args: argparse.Namespace) -> int:
        self._validate_exclusive_options(args)

        loaded = load_text(args.path, encoding=args.encoding)
        text = _normalize(loaded.text)

        if args.similar:
            frequencies = self._frequencies_from_similar(text, args)
        else:
            frequencies = self._frequencies_from_words(text, args)

        if not frequencies:
            raise SystemExit(
                "集計対象が0件です。入力が空か、全ての単語がストップワードで除去された"
                "可能性があります。--no-default-stopwords を試してください。"
            )

        font_path = Path(args.font) if args.font else _DEFAULT_FONT
        if not font_path.exists():
            raise SystemExit(f"フォントが見つかりません: {font_path}")

        wc = WordCloud(font_path=str(font_path), width=800, height=600, background_color="white")
        result = wc.generate_from_frequencies(frequencies).to_image()

        output_path = save_result(loaded, result, "cwc", args.output)
        print(describe_output(output_path))
        return 0

    def _validate_exclusive_options(self, args: argparse.Namespace) -> None:
        if args.semantic and (args.wakachi or args.hinshi is not None):
            raise SystemExit("--semantic は -w / --hinshi と同時に指定できません")
        if args.similar and (args.semantic or args.wakachi or args.hinshi is not None):
            raise SystemExit("--similar は --semantic / -w / --hinshi と同時に指定できません")

    def _frequencies_from_words(self, text: str, args: argparse.Namespace) -> dict[str, int]:
        use_wakachi = args.wakachi or args.hinshi is not None
        if args.hinshi is not None and not args.wakachi:
            logger.info("--hinshi 指定のため分かち書き経路を自動的に有効化します")

        if use_wakachi:
            words = self._tokens_from_wakachi(text, args)
        else:
            words = _split_default(text)
            if args.semantic:
                words = self._apply_synonyms(words, args)

        stopwords = _resolve_stopwords(args)
        words = [w for w in words if w not in stopwords]

        frequencies: dict[str, int] = {}
        for word in words:
            frequencies[word] = frequencies.get(word, 0) + 1
        return frequencies

    def _frequencies_from_similar(self, text: str, args: argparse.Namespace) -> dict[str, int]:
        sentences = [s for s in _SENTENCE_SPLIT_PATTERN.split(text) if s]
        if not sentences:
            return {}

        if len(sentences) > _SIMILAR_MAX_SENTENCES:
            logger.warning(
                "--similar の入力文数が上限(%d)を超えたため、先頭%d件のみ使用します（全%d件）",
                _SIMILAR_MAX_SENTENCES,
                _SIMILAR_MAX_SENTENCES,
                len(sentences),
            )
            sentences = sentences[:_SIMILAR_MAX_SENTENCES]

        vectors = embed_sentences(sentences, model_name=args.similar_model)
        distance_matrix = 1.0 - (vectors @ vectors.T)
        labels = agglomerative_average_linkage(distance_matrix, args.similar_threshold)

        clusters: dict[int, list[str]] = {}
        for sentence, label in zip(sentences, labels, strict=True):
            clusters.setdefault(int(label), []).append(sentence)

        max_length = args.similar_max_length
        frequencies: dict[str, int] = {}
        for members in clusters.values():
            counts: dict[str, int] = {}
            for s in members:
                counts[s] = counts.get(s, 0) + 1
            best_count = max(counts.values())
            candidates = [s for s, c in counts.items() if c == best_count]
            representative = min(candidates, key=len)

            display = representative
            if max_length > 0 and len(display) > max_length:
                display = display[:max_length] + "…"
                logger.info(
                    "代表文を切り詰めました: %s -> %s（元クラスタ件数=%d）",
                    representative,
                    display,
                    len(members),
                )

            if display in frequencies:
                logger.info(
                    "切り詰め後の表示が別クラスタと衝突したため頻度を合算します: %s", display
                )
            frequencies[display] = frequencies.get(display, 0) + len(members)

        return frequencies

    def _tokens_from_wakachi(self, text: str, args: argparse.Namespace) -> list[str]:
        user_dict = _resolve_user_dict(args)
        tokens = _split_wakachi(text, user_dict)

        hinshi_filter: set[str] | None = None
        if args.hinshi is not None:
            hinshi_filter = set()
            for chunk in args.hinshi:
                hinshi_filter.update(h.strip() for h in chunk.split(",") if h.strip())
            unknown = hinshi_filter - set(_HINSHI_CHOICES)
            if unknown:
                raise SystemExit(
                    f"未知の品詞名です: {', '.join(sorted(unknown))}"
                    f"（指定可能: {', '.join(_HINSHI_CHOICES)}）"
                )

        words = []
        for surface, base_form, hinshi in tokens:
            if hinshi_filter is not None and hinshi not in hinshi_filter:
                continue
            if hinshi_filter is not None:
                words.append(base_form if base_form != "*" else surface)
            else:
                words.append(surface)
        return words

    def _apply_synonyms(self, words: list[str], args: argparse.Namespace) -> list[str]:
        synonym_dict = _resolve_synonym_dict(args)
        if synonym_dict is None:
            return words

        mapping = _load_synonym_map(synonym_dict)
        result = []
        for word in words:
            representative = mapping.get(word)
            if representative is not None and representative != word:
                logger.info("同義語として寄せました: %s -> %s", word, representative)
                result.append(representative)
            else:
                result.append(word)
        return result
