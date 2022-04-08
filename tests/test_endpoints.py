"""Unit tests for Notion API endpoints.

These are considered "live" tests, as they will interact directly with the Notion API.

Running these tests requires setting specific environment variables.  If these
variables are not defined, the tests will be skipped.

Required environment variables:
  - `NOTION_AUTH_TOKEN`: the integration token used for testing.
  - `NOTION_TEST_AREA`: a page ID that can be used for testing
"""

import logging
import os
import unittest
from datetime import datetime, timezone

import notional
from notional import blocks, records

# keep logging output to a minumim for testing
logging.basicConfig(level=logging.FATAL)


class EndpointTest(object):
    """Base class for live tests (manage connectivity to Notion)."""

    cleanup_pages = []

    def setUp(self):
        """Configure resources needed by these tests."""

        auth_token = os.getenv("NOTION_AUTH_TOKEN", None)

        if auth_token is None:
            raise unittest.SkipTest("missing NOTION_AUTH_TOKEN")

        parent_id = os.getenv("NOTION_TEST_AREA", None)

        if parent_id is None:
            raise unittest.SkipTest("missing NOTION_TEST_AREA")

        self.notion = notional.connect(auth=auth_token)
        self.parent = records.PageRef(page_id=parent_id)

    def tearDown(self):
        """Teardown resources created by these tests."""
        for page in self.cleanup_pages:
            self.notion.pages.delete(page)

        self.cleanup_pages.clear()

    def create_temp_page(self, title=None, children=None):
        """Create a temporary page on the server.

        This page will be deleted during teardown of the test.
        """

        page = self.notion.pages.create(
            parent=self.parent, title=title, children=children
        )

        self.cleanup_pages.append(page)

        return page


class BlockEndpointTests(EndpointTest, unittest.TestCase):
    """Test live blocks through the Notion API."""

    def confirm_blocks(self, page, *blocks):
        """Confirm the expected blocks in a given page."""

        num_blocks = 0

        for block in self.notion.blocks.children.list(parent=page):
            self.assertEqual(block, blocks[num_blocks])
            num_blocks += 1

        self.assertEqual(num_blocks, len(blocks))

    def test_create_empty_block(self):
        """Create an empty block and confirm its contents."""
        para = blocks.Paragraph()
        page = self.create_temp_page(title="test_CreateEmptyBlock", children=[para])

        self.confirm_blocks(page, para)

    def test_create_basic_text_block(self):
        """Create a basic block and verify content."""

        page = self.create_temp_page(title="test_CreateBasicTextBlock")

        para = blocks.Paragraph.from_text("Hello World")
        self.notion.blocks.children.append(page, para)

        self.confirm_blocks(page, para)


class PageEndpointTests(EndpointTest, unittest.TestCase):
    """Test live pages through the Notion API."""

    def test_blank_page(self):
        """Create an empty page in Notion."""

        page = self.create_temp_page()
        new_page = self.notion.pages.retrieve(page_id=page.id)

        self.assertEqual(page.id, new_page.id)
        self.assertIsNone(new_page.Title)

        diff = datetime.now(timezone.utc) - new_page.created_time
        self.assertLessEqual(diff.total_seconds(), 60)

    def test_page_parent(self):
        """Verify page parent references."""

        page = self.create_temp_page()

        self.assertEqual(self.parent, page.parent)


class SearchEndpointTests(EndpointTest, unittest.TestCase):
    """Test searching through the Notion API."""

    def test_simple_search(self):
        """Make sure search returns some results."""

        search = self.notion.search()

        num_results = 0

        for result in search.execute():
            self.assertIsInstance(result, records.Record)
            num_results += 1

        # sanity check to make sure some results came back
        self.assertGreater(num_results, 0)
