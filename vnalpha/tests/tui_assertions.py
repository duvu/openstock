from __future__ import annotations


def assert_workspace_regions(app) -> None:
    output = app.query_one("#output-stream")
    composer = app.query_one("#composer-input")
    main_body = app.query_one("#main-body")
    footer = app.query_one("#footer-hint")
    todo = app.query_one("#todo-panel")

    assert output.region.bottom <= composer.region.y
    assert output.region.bottom <= main_body.region.bottom
    assert composer.region.bottom <= app.size.height
    if footer.display:
        assert composer.region.bottom <= footer.region.y
    if todo.display:
        assert todo.region.bottom <= main_body.region.bottom
