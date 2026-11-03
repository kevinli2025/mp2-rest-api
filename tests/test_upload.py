from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app, storage


@pytest.fixture
def client():
    storage.clear()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    storage.clear()


@pytest.mark.parametrize(
    ('contents', 'rows', 'columns'),
    [(b'value\n1\n', 1, ['value']),
     ((Path(__file__).parents[1] / 'fixtures/sample_data.csv').read_bytes(),
      6, ['student_id', 'score'])],
)
def test_upload_returns_dataset_metadata(client, contents, rows, columns):
    response = client.post(
        '/upload', files={'file': ('sample_data.csv', contents, 'text/csv')}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        'id': 1,
        'filename': 'sample_data.csv',
        'rows': rows,
        'columns': len(columns),
        'column_names': columns,
    }
    assert len(storage.get(1)) == rows


@pytest.mark.parametrize('limit', [2, 100])
def test_retrieve_dataset(client, limit):
    contents = (Path(__file__).parents[1] / 'fixtures/sample_data.csv').read_bytes()
    uploaded = client.post('/upload', files={'file': ('sample_data.csv', contents, 'text/csv')})
    dataset_id = uploaded.json()['id']
    response = client.get(f'/datasets/{dataset_id}', params={'limit': limit})
    assert response.status_code == 200, response.text
    expected = [
        {'student_id': 1, 'score': '80'},
        {'student_id': 2, 'score': '90'},
        {'student_id': 2, 'score': '90'},
        {'student_id': 3, 'score': None},
        {'student_id': 4, 'score': 'unknown'},
        {'student_id': 5, 'score': '85'},
    ]
    assert response.json() == {'id': dataset_id, 'data': expected[:limit], 'total_rows': 6}
    assert len(storage.get(dataset_id)) == 6


def test_retrieve_missing_dataset(client):
    assert client.get('/datasets/999').status_code == 404


def test_process_and_retrieve(client):
    contents = (Path(__file__).parents[1] / 'fixtures/sample_data.csv').read_bytes()
    dataset_id = client.post('/upload', files={'file': ('sample_data.csv', contents)}).json()['id']
    response = client.post(f'/datasets/{dataset_id}/process', json={
        'validation': {'required_columns': ['student_id', 'score'], 'numeric_columns': ['score']}
    })
    assert response.status_code == 200, response.text
    assert response.json() == {
        'id': dataset_id, 'validation_rows_removed': 1,
        'cleaning_report': {'rows_before': 5, 'rows_after': 3, 'rows_removed': 2,
                            'columns_before': 2, 'columns_after': 2, 'columns_removed': 0}
    }
    assert client.get(f'/datasets/{dataset_id}').json() == {
        'id': dataset_id, 'total_rows': 3,
        'data': [{'student_id': 1, 'score': 80}, {'student_id': 2, 'score': 90},
                 {'student_id': 5, 'score': 85}]
    }


@pytest.mark.parametrize('config', [
    {'validation': {'numeric_columns': ['missing']}},
    {'validation': {'required_columns': ['missing']}},
    {'processing': {'missing': {'axis': 'unsupported'}}},
    {'validation': {'numeric_columns': ['score']},
     'processing': {'outliers': {'enabled': True, 'method': 'unsupported'}}},
])
def test_failed_processing_preserves_dataset(client, config):
    contents = (Path(__file__).parents[1] / 'fixtures/sample_data.csv').read_bytes()
    dataset_id = client.post('/upload', files={'file': ('sample_data.csv', contents)}).json()['id']
    before = storage.get(dataset_id)
    response = client.post(f'/datasets/{dataset_id}/process', json=config)
    assert response.status_code == 400, response.text
    assert storage.get(dataset_id).equals(before)


def test_process_missing_dataset(client):
    assert client.post('/datasets/999/process', json={}).status_code == 404
