import argparse
from pathlib import Path

import pytest

from workpytools.processing import cwc as cwc_module
from workpytools.processing.cwc import CwcProcessor, _normalize, _split_default


def _base_args(**overrides: object) -> argparse.Namespace:
    defaults = dict(
        path=None,
        output=None,
        encoding=None,
        wakachi=False,
        hinshi=None,
        semantic=False,
        synonym_dict=None,
        no_synonym_dict=False,
        user_dict=None,
        no_user_dict=False,
        stopwords=None,
        stopwords_file=None,
        no_default_stopwords=False,
        font=None,
        similar=False,
        similar_threshold=0.2,
        similar_model="paraphrase-multilingual-MiniLM-L12-v2",
        similar_max_length=10,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture(autouse=True)
def _fake_font(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Avoid depending on the real Meiryo font file during tests."""
    font_dir = Path(__import__("wordcloud").__file__).parent / "DroidSansMono.ttf"
    monkeypatch.setattr(cwc_module, "_DEFAULT_FONT", font_dir)


def test_run_saves_output_next_to_input(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い。散歩した。", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src))
    result = proc.run(args)

    expected = tmp_path / "memo_cwc.png"
    assert result == 0
    assert expected.exists()


def test_run_with_explicit_output(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い。", encoding="utf-8")
    out = tmp_path / "custom.png"

    proc = CwcProcessor()
    args = _base_args(path=str(src), output=str(out))
    proc.run(args)

    assert out.exists()


def test_run_from_clipboard_file_object_saves_to_tmpdir_and_copies_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    copied_src = tmp_path / "copied.txt"
    copied_src.write_text("今日は天気が良い。", encoding="utf-8")
    tmpdir = tmp_path / "tmp"
    tmpdir.mkdir()

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None
    )

    def fake_is_available(fmt: int) -> bool:
        import win32clipboard as wc

        return fmt == wc.CF_HDROP

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.IsClipboardFormatAvailable",
        fake_is_available,
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.GetClipboardData",
        lambda fmt: [str(copied_src)],
    )
    monkeypatch.setattr("workpytools.common.output.tempfile.gettempdir", lambda: str(tmpdir))
    clipboard_calls = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_file_to_clipboard", lambda p: clipboard_calls.append(p)
    )

    proc = CwcProcessor()
    args = _base_args(path=None)
    proc.run(args)

    expected = tmpdir / "copied_cwc.png"
    assert expected.exists()
    assert clipboard_calls == [expected]


def test_run_from_clipboard_plain_text_copies_image_no_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.OpenClipboard", lambda: None
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.CloseClipboard", lambda: None
    )

    def fake_is_available(fmt: int) -> bool:
        import win32clipboard as wc

        return fmt == wc.CF_UNICODETEXT

    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.IsClipboardFormatAvailable",
        fake_is_available,
    )
    monkeypatch.setattr(
        "workpytools.common.clipboard.win32clipboard.GetClipboardData",
        lambda fmt: "今日は天気が良い。",
    )
    monkeypatch.chdir(tmp_path)
    copied = []
    monkeypatch.setattr(
        "workpytools.common.output.copy_image_to_clipboard", lambda img: copied.append(img)
    )

    proc = CwcProcessor()
    args = _base_args(path=None)
    proc.run(args)

    assert not list(tmp_path.glob("*.png"))
    assert len(copied) == 1


# --- 分割・正規化 ---


def test_split_default_on_spaces_tabs_newlines() -> None:
    assert _split_default("今日 は\t天気\nが良い") == ["今日", "は", "天気", "が良い"]


def test_split_default_on_period_and_brackets() -> None:
    assert _split_default("今日は天気が良い。（特になし）明日は？") == [
        "今日は天気が良い",
        "特になし",
        "明日は？",
    ]


def test_split_default_keeps_touten() -> None:
    assert _split_default("今日は、天気が良い") == ["今日は、天気が良い"]


def test_normalize_fullwidth_and_kana_kanji() -> None:
    assert _normalize("ＡＢＣ１２３") == "ABC123"
    assert _normalize("無し") == "なし"
    assert _normalize("有る") == "ある"


def test_run_with_wakachi(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良いので散歩した", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), wakachi=True)
    result = proc.run(args)

    assert result == 0
    assert (tmp_path / "memo_cwc.png").exists()


def test_hinshi_filters_to_meishi_only(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良いので散歩した", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), hinshi=["名詞"])
    result = proc.run(args)

    assert result == 0


def test_hinshi_auto_enables_wakachi(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良いので散歩した", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), hinshi=["名詞"], wakachi=False)
    with caplog.at_level("INFO"):
        proc.run(args)

    assert "自動的に有効化" in caplog.text


def test_hinshi_multiple_and_comma_separated() -> None:
    proc = CwcProcessor()
    args = _base_args(hinshi=["名詞,動詞"])
    words = proc._tokens_from_wakachi("今日は天気が良いので散歩した", args)
    assert words  # 名詞・動詞のみ残る


def test_hinshi_uses_base_form() -> None:
    proc = CwcProcessor()
    args = _base_args(hinshi=["動詞"])
    words = proc._tokens_from_wakachi("使っています", args)
    assert "使う" in words


def test_hinshi_unknown_raises_system_exit() -> None:
    proc = CwcProcessor()
    args = _base_args(hinshi=["存在しない品詞"])
    with pytest.raises(SystemExit):
        proc._tokens_from_wakachi("テスト", args)


def test_semantic_and_wakachi_are_exclusive(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), semantic=True, wakachi=True)
    with pytest.raises(SystemExit):
        proc.run(args)


def test_semantic_and_hinshi_are_exclusive(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), semantic=True, hinshi=["名詞"])
    with pytest.raises(SystemExit):
        proc.run(args)


def test_semantic_merges_synonyms(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("特になし\n特にない\nない\n", encoding="utf-8")

    proc = CwcProcessor()
    words = _split_default(_normalize(src.read_text(encoding="utf-8")))
    args = _base_args(semantic=True)
    merged = proc._apply_synonyms(words, args)

    assert merged == ["なし", "なし", "なし"]


def test_semantic_disabled_keeps_variants(tmp_path: Path) -> None:
    words = ["特になし", "特にない", "ない"]
    proc = CwcProcessor()
    args = _base_args(semantic=False, no_synonym_dict=True)
    result = proc._apply_synonyms(words, args)
    assert result == words


def test_no_synonym_dict_disables_merging() -> None:
    proc = CwcProcessor()
    args = _base_args(no_synonym_dict=True)
    words = ["特になし", "特にない"]
    result = proc._apply_synonyms(words, args)
    assert result == words


def test_synonym_dict_missing_file_warns_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    proc = CwcProcessor()
    args = _base_args(synonym_dict="C:/does/not/exist.tsv")
    with caplog.at_level("WARNING"):
        result = proc._apply_synonyms(["特になし"], args)

    assert result == ["特になし"]
    assert "見つからない" in caplog.text


def test_user_dict_missing_file_warns_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    args = _base_args(user_dict="C:/does/not/exist.dic")
    with caplog.at_level("WARNING"):
        result = cwc_module._resolve_user_dict(args)

    assert result is None
    assert "見つからない" in caplog.text


def test_no_user_dict_disables_dict() -> None:
    args = _base_args(no_user_dict=True)
    assert cwc_module._resolve_user_dict(args) is None


# --- ストップワード ---


def test_default_stopwords_contains_expected_entries() -> None:
    args = _base_args()
    stopwords = cwc_module._resolve_stopwords(args)
    assert "こと" in stopwords
    assert "する" in stopwords
    assert "の" in stopwords


def test_stopwords_option_adds_words() -> None:
    args = _base_args(stopwords=["カスタム,除外語"])
    stopwords = cwc_module._resolve_stopwords(args)
    assert "カスタム" in stopwords
    assert "除外語" in stopwords


def test_stopwords_file_adds_words(tmp_path: Path) -> None:
    path = tmp_path / "stop.txt"
    path.write_text("独自単語\n", encoding="utf-8")
    args = _base_args(stopwords_file=str(path))
    stopwords = cwc_module._resolve_stopwords(args)
    assert "独自単語" in stopwords


def test_no_default_stopwords_disables_defaults_and_english() -> None:
    args = _base_args(no_default_stopwords=True)
    stopwords = cwc_module._resolve_stopwords(args)
    assert "こと" not in stopwords
    assert "the" not in stopwords


def test_english_stopwords_applied_by_default() -> None:
    args = _base_args()
    stopwords = cwc_module._resolve_stopwords(args)
    assert "the" in stopwords


def test_empty_result_raises_system_exit(tmp_path: Path) -> None:
    src = tmp_path / "empty.txt"
    src.write_text("", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src))
    with pytest.raises(SystemExit):
        proc.run(args)


# --- エンコーディング ---


def test_cp932_file_is_read_via_fallback(tmp_path: Path) -> None:
    src = tmp_path / "sjis.txt"
    src.write_bytes("今日は天気が良い".encode("cp932"))

    proc = CwcProcessor()
    args = _base_args(path=str(src))
    result = proc.run(args)

    assert result == 0


# --- --similar ---


def _fake_embed(monkeypatch: pytest.MonkeyPatch, vectors: dict) -> None:
    import numpy as np

    def fake_embed_sentences(sentences, model_name=None):
        return np.array([vectors[s] for s in sentences])

    monkeypatch.setattr(cwc_module, "embed_sentences", fake_embed_sentences)


def test_similar_sentence_split_on_period_newline_and_halfwidth_marks() -> None:
    from workpytools.processing.cwc import _SENTENCE_SPLIT_PATTERN

    text = "今日は天気が良い。散歩した\n特になし!他は?"
    parts = [s for s in _SENTENCE_SPLIT_PATTERN.split(text) if s]
    assert parts == ["今日は天気が良い", "散歩した", "特になし", "他は"]


def test_similar_clusters_by_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    vectors = {
        "文A": np.array([1.0, 0.0]),
        "文Aに似た文": np.array([0.99, 0.01]),
        "全く違う文": np.array([0.0, 1.0]),
    }
    for v in vectors.values():
        v /= np.linalg.norm(v)
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_threshold=0.2)
    freq = proc._frequencies_from_similar("文A。文Aに似た文。全く違う文", args)

    assert sum(freq.values()) == 3
    assert len(freq) == 2  # 似た2文がまとまり、違う文は分離


def test_similar_representative_is_most_frequent_then_shortest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import numpy as np

    vectors = {
        "特になし": np.array([1.0, 0.0]),
        "特に何もありません": np.array([0.99, 0.01]),
    }
    for v in vectors.values():
        v /= np.linalg.norm(v)
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_threshold=0.5)
    freq = proc._frequencies_from_similar("特になし。特に何もありません", args)

    assert list(freq.keys()) == ["特になし"]
    assert freq["特になし"] == 2


def test_similar_max_length_truncates_with_ellipsis(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    sentence = "これはとても長い文章のテストです"
    vectors = {sentence: np.array([1.0, 0.0])}
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_max_length=5)
    freq = proc._frequencies_from_similar(sentence, args)

    assert list(freq.keys()) == [sentence[:5] + "…"]


def test_similar_max_length_zero_disables_truncation(monkeypatch: pytest.MonkeyPatch) -> None:
    import numpy as np

    sentence = "これはとても長い文章のテストです"
    vectors = {sentence: np.array([1.0, 0.0])}
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_max_length=0)
    freq = proc._frequencies_from_similar(sentence, args)

    assert list(freq.keys()) == [sentence]


def test_similar_truncation_collision_merges_frequencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import numpy as np

    vectors = {
        "同じ接頭辞だが別の文A": np.array([1.0, 0.0]),
        "同じ接頭辞だが別の文B": np.array([0.0, 1.0]),
    }
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_threshold=-1.0, similar_max_length=6)
    freq = proc._frequencies_from_similar(
        "同じ接頭辞だが別の文A。同じ接頭辞だが別の文B", args
    )

    assert list(freq.keys()) == ["同じ接頭辞だ…"]
    assert freq["同じ接頭辞だ…"] == 2


def test_similar_and_semantic_are_exclusive(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), similar=True, semantic=True)
    with pytest.raises(SystemExit):
        proc.run(args)


def test_similar_and_wakachi_are_exclusive(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), similar=True, wakachi=True)
    with pytest.raises(SystemExit):
        proc.run(args)


def test_similar_and_hinshi_are_exclusive(tmp_path: Path) -> None:
    src = tmp_path / "memo.txt"
    src.write_text("今日は天気が良い", encoding="utf-8")

    proc = CwcProcessor()
    args = _base_args(path=str(src), similar=True, hinshi=["名詞"])
    with pytest.raises(SystemExit):
        proc.run(args)


def test_similar_empty_input_returns_empty_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = CwcProcessor()
    args = _base_args()
    freq = proc._frequencies_from_similar("", args)
    assert freq == {}


def test_embedding_module_does_not_import_onnxruntime_or_tokenizers_at_top_level() -> None:
    import workpytools.common.embedding as mod

    src = mod.__file__
    assert src is not None
    with open(src, encoding="utf-8") as f:
        content = f.read()
    top_level = content.split("def ")[0]
    assert "import onnxruntime" not in top_level
    assert "import tokenizers" not in top_level
    assert "from tokenizers" not in top_level


def test_similar_sentences_exceeding_limit_are_truncated_with_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import numpy as np

    monkeypatch.setattr(cwc_module, "_SIMILAR_MAX_SENTENCES", 3)

    vectors = {f"文{i}": np.array([float(i), 1.0]) for i in range(5)}
    _fake_embed(monkeypatch, vectors)

    proc = CwcProcessor()
    args = _base_args(similar_threshold=-1.0)
    text = "。".join(vectors.keys())
    with caplog.at_level("WARNING"):
        freq = proc._frequencies_from_similar(text, args)

    assert sum(freq.values()) == 3
    assert "上限" in caplog.text
