"""Tests for GitHub-style task-list rendering.

Covers:
- `- [ ]` renders as an unchecked ballot box, `- [x]`/`- [X]` as a checked one.
- Rewritten items gain the task-list-item class and a task-checkbox span.
- Non-task list items are left untouched.
- Items with block content (wrapped in <p>) are handled.
- The transform survives the full pipeline (parse_text) and both renderers.
"""

from brandx.config.resolver import resolve
from brandx.render.email import render_email
from brandx.render.pipeline import parse_text
from brandx.render.tasklists import _CHECKED, _UNCHECKED, process_tasklists


class TestProcessTasklists:
    def test_unchecked(self):
        html = process_tasklists("<ul>\n<li>[ ] Public</li>\n</ul>")
        assert 'class="task-list-item"' in html
        assert _UNCHECKED in html
        assert _CHECKED not in html
        assert 'aria-label="unchecked"' in html
        assert "[ ]" not in html

    def test_checked(self):
        html = process_tasklists("<ul>\n<li>[x] Internal</li>\n</ul>")
        assert _CHECKED in html
        assert 'aria-label="checked"' in html
        assert "[x]" not in html

    def test_capital_x_checked(self):
        html = process_tasklists("<ul>\n<li>[X] Capital</li>\n</ul>")
        assert _CHECKED in html
        assert "[X]" not in html

    def test_non_task_item_untouched(self):
        html = process_tasklists("<ul>\n<li>regular item</li>\n</ul>")
        assert "task-list-item" not in html
        assert "task-checkbox" not in html

    def test_block_content_item(self):
        html = process_tasklists(
            "<ul>\n<li>\n<p>[x] <strong>Bold</strong> task</p>\n</li>\n</ul>"
        )
        assert 'class="task-list-item"' in html
        assert _CHECKED in html
        assert "<strong>Bold</strong>" in html

    def test_existing_class_merged(self):
        html = process_tasklists('<li class="foo">[ ] Item</li>')
        assert 'class="foo task-list-item"' in html

    def test_marker_only_at_item_start(self):
        # A bracketed token mid-text is not a task marker.
        html = process_tasklists("<ul>\n<li>see [x] in the spec</li>\n</ul>")
        assert "task-list-item" not in html


class TestPipelineIntegration:
    def test_task_list_through_pipeline(self):
        doc = parse_text("# T\n\n- [ ] Public\n- [x] Internal\n")
        assert doc.body_html.count('class="task-list-item"') == 2
        assert _UNCHECKED in doc.body_html
        assert _CHECKED in doc.body_html

    def test_email_suppresses_bullet_inline(self):
        cfg = resolve(home_config={}, os_name_fn=lambda: "Test User")
        doc = parse_text("# T\n\n- [ ] Public\n")
        html = render_email(doc, cfg)
        assert "list-style:none" in html
        # The li must carry exactly one style attribute, not two.
        li = next(line for line in html.splitlines() if "task-list-item" in line)
        assert li.count("style=") == 1
