from __future__ import annotations


def assert_workspace_regions(app) -> None:
    output = app.query_one("#output-stream")
    composer = app.query_one("#composer-input")
    main_body = app.query_one("#main-body")
    footer = app.query_one("#footer-hint")
    drawer = app.query_one("#debug-log-drawer")
    output_column = app.query_one("#output-column")

    assert output.region.bottom <= composer.region.y
    assert output.region.bottom <= main_body.region.bottom
    assert output_column.region.width == main_body.region.width
    assert composer.region.bottom <= app.size.height
    if footer.display:
        assert composer.region.bottom <= footer.region.y
    if drawer.display:
        assert output.region.bottom <= drawer.region.y
        assert drawer.region.bottom <= composer.region.y
        assert drawer.region.bottom <= main_body.region.bottom
