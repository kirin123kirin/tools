from __future__ import annotations


def markdown_to_html_fragment(markdown_text: str) -> str:
    """Render Markdown to an HTML fragment (no <html>/<body> wrapper).

    Uses the commonmark preset with the table extension enabled (disabled by
    default in markdown-it-py). commonmark's html=True also lets raw HTML in
    the Markdown source pass through untouched.
    """
    from markdown_it import MarkdownIt

    md = MarkdownIt("commonmark").enable("table")
    rendered: str = md.render(markdown_text)
    return rendered
