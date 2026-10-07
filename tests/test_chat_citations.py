"""Regression checks for citations emitted by Gemini."""
import asyncio
from unittest.mock import AsyncMock, patch

from backend.services.chat import validate_citations, handle_chat


def test_grouped_citations_expand_and_invalid_ids_are_removed():
    answer = validate_citations('Evidence [E1, E2, E99, R1, R9]. Single [E2].', 2, 1)
    assert answer == 'Evidence [E1] [E2] [R1]. Single [E2].'


def test_non_citation_brackets_are_preserved():
    assert validate_citations('[note] [E8] [R2]', 0, 0) == '[note]'


def test_old_grouped_cache_is_regenerated_with_complete_metadata():
    episode = {'signal_id': 'test-signal', 'quote': 'Search failed', 'source': 'reddit'}
    with patch('backend.services.chat.get_cached_response', AsyncMock(return_value={'answer':'Cached [E1, E2]'})), \
         patch('backend.services.chat.rewrite_query', return_value='search'), \
         patch('backend.services.chat.embed_query', return_value=[1.0]), \
         patch('backend.services.chat.retrieve_episodes', AsyncMock(return_value=[episode])), \
         patch('backend.services.chat.retrieve_literature', AsyncMock(return_value=[])), \
         patch('backend.services.chat.get_stats_snapshot', AsyncMock(return_value={})), \
         patch('backend.services.chat.generate_answer', return_value='New [E1, E99]'), \
         patch('backend.services.chat.cache_response', AsyncMock()):
        response = asyncio.run(handle_chat('question', object()))
    assert response['answer'] == 'New [E1]'
    assert response['cached'] is False
    assert [citation['id'] for citation in response['citations']] == ['E1']


def test_gemini_requests_have_bounded_timeout_and_no_hidden_sdk_retries():
    from backend.services.chat import _call_gemini
    with patch('backend.services.chat._key_pool.acquire', return_value='test-key'), \
         patch('backend.services.chat.genai.Client') as client:
        client.return_value.models.generate_content.return_value.text = 'answer'
        assert _call_gemini('question') == 'answer'
        options = client.call_args.kwargs['http_options']
    assert options.timeout == 30000
    assert options.retry_options.attempts == 1
