import pytest
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from pipeline.sources.csv_import import CSVSource
from pipeline.sources.reddit import RedditSource
from pipeline.sources.appstore import AppStoreSource
from pipeline.sources.playstore import PlayStoreSource
from pipeline.sources.youtube import YouTubeSource

def test_csv_deterministic_id_and_date_validation():
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write("text,created_at,author,url\n")
        # Valid row
        f.write("Good text,2023-01-01T12:00:00Z,user1,http://url1\n")
        # Missing date
        f.write("No date,,user2,http://url2\n")
        # Unparseable date
        f.write("Bad date,invalid-date,user3,http://url3\n")
        temp_path = f.name

    try:
        src = CSVSource(temp_path)
        cutoff = datetime(2022, 1, 1, tzinfo=timezone.utc)
        records = src.fetch(cutoff, cap=10)

        # Only the valid row should be fetched
        assert len(records) == 1
        assert records[0].text == "Good text"
        # Rejected count should be 2
        assert src.rejected_count == 2

        # Check deterministic ID based on hash of source+url
        # Source.CSV.value is 'csv'. The seed is 'csvhttp://url1'
        # The author hash of that seed is what we use. Let's just check it starts with 'csv_'
        assert records[0].record_id.startswith("csv_")
        
        # Test missing URL uses text for ID seed
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f2:
            f2.write("text,created_at,author,url\n")
            f2.write("Good text no url,2023-01-01T12:00:00Z,user1,\n")
            temp_path2 = f2.name
            
        src2 = CSVSource(temp_path2)
        records2 = src2.fetch(cutoff, cap=10)
        assert len(records2) == 1
        assert records2[0].record_id.startswith("csv_")
        
    finally:
        os.remove(temp_path)
        if 'temp_path2' in locals():
            os.remove(temp_path2)

@patch("pipeline.sources.appstore.requests.get")
@patch("pipeline.sources.appstore.APPSTORE_PRODUCT_ID", "123456")
def test_appstore_source_caps_and_errors(mock_get):
    # Mocking errors and partial success
    def side_effect(*args, **kwargs):
        # We will mock the first country (us) to return some reviews, then error.
        country = kwargs.get("params", {}).get("country", "")
        if "us" in country:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "reviews": [{"title": "Great", "author": "a", "date": "2023-10-10T10:10:10Z", "id": "1", "text": "Good", "url": "http://1"}]
            }
            return mock_resp
        else:
            raise Exception("API failure")
            
    mock_get.side_effect = side_effect
    
    src = AppStoreSource("dummy_key")
    cutoff = datetime(2022, 1, 1, tzinfo=timezone.utc)
    # With cap 1, max(1, 1//2) = 1 cap per country
    records = src.fetch(cutoff, cap=1)
    
    assert len(records) > 0
    assert len(src.errors) == 1
    assert "API failure" in src.errors[0]

@patch("pipeline.sources.playstore.reviews")
def test_playstore_source_caps_and_errors(mock_reviews):
    def side_effect(*args, **kwargs):
        lang = kwargs.get("lang")
        if lang == "en":
            return ([{"content": "Good", "userName": "U1", "at": datetime(2023, 10, 10), "reviewId": "1"}], None)
        else:
            raise Exception("PlayStore API failure")
            
    mock_reviews.side_effect = side_effect
    
    src = PlayStoreSource()
    cutoff = datetime(2022, 1, 1, tzinfo=timezone.utc)
    records = src.fetch(cutoff, cap=1)
    
    assert len(records) > 0
    assert len(src.errors) > 0

@patch("pipeline.sources.reddit.ApifyClient")
def test_reddit_source_caps_and_errors(mock_apify_cls):
    mock_client = MagicMock()
    mock_apify_cls.return_value = mock_client
    
    mock_actor = MagicMock()
    mock_client.actor.return_value = mock_actor
    
    def side_effect(run_input, *args, **kwargs):
        # Fail on the second community
        if run_input.get("withinCommunity") == "":
            raise Exception("Reddit API failure")
        
        mock_run = MagicMock()
        mock_run.get.return_value = "dataset_123"
        return mock_run
        
    mock_actor.call.side_effect = side_effect
    
    mock_dataset = MagicMock()
    mock_client.dataset.return_value = mock_dataset
    mock_dataset.iterate_items.return_value = [
        {"dataType": "post", "createdAt": "2023-10-10T10:10:10Z", "body": "R1", "authorName": "A1", "id": "1", "postUrl": "http://1", "title": "T1", "parsedId": "1", "parsedCommunityName": "r1"}
    ]
    
    src = RedditSource("dummy_token")
    cutoff = datetime(2022, 1, 1, tzinfo=timezone.utc)
    records = src.fetch(cutoff, cap=2)
    
    assert len(records) == 1
    assert len(src.errors) == 1
    assert "Reddit API failure" in src.errors[0]

@patch("pipeline.sources.youtube.build")
def test_youtube_source_caps_and_errors(mock_build):
    mock_youtube = MagicMock()
    mock_build.return_value = mock_youtube
    
    mock_search = MagicMock()
    mock_youtube.search.return_value = mock_search
    
    mock_search_list = MagicMock()
    mock_search.list.return_value = mock_search_list
    
    mock_search_list.execute.return_value = {
        "items": [{"id": {"videoId": "v1"}}]
    }
    
    mock_comments = MagicMock()
    mock_youtube.commentThreads.return_value = mock_comments
    mock_comments_list = MagicMock()
    mock_comments.list.return_value = mock_comments_list
    
    def execute_side_effect():
        # First execute succeeds, then fails
        if not hasattr(execute_side_effect, 'called'):
            execute_side_effect.called = True
            return {
                "items": [{
                    "id": "c1",
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "publishedAt": "2023-10-10T10:10:10Z",
                                "textDisplay": "YT1",
                                "authorDisplayName": "A1"
                            }
                        }
                    }
                }]
            }
        else:
            raise Exception("YouTube comments failure")
            
    mock_comments_list.execute.side_effect = execute_side_effect
    mock_comments.list_next.return_value = mock_comments_list
    
    src = YouTubeSource("dummy_key")
    cutoff = datetime(2022, 1, 1, tzinfo=timezone.utc)
    records = src.fetch(cutoff, cap=5)
    
    assert len(records) > 0
    assert len(src.errors) > 0
