from app.unsubscribe_agent import parse_list_unsubscribe, find_unsubscribe_links_in_html

def test_parse_list_unsubscribe_http_and_mailto():
    headers = {"list-unsubscribe": "<mailto:unsubscribe@example.com>, <https://example.com/unsub?id=1>"}
    links = parse_list_unsubscribe(headers)
    assert any(l.kind == "mailto" for l in links)
    assert any(l.kind == "http" for l in links)

def test_find_unsubscribe_links_in_html():
    html = '<html><body><a href="https://x.com/unsubscribe">Unsubscribe</a></body></html>'
    links = find_unsubscribe_links_in_html(html)
    assert links == ["https://x.com/unsubscribe"]
