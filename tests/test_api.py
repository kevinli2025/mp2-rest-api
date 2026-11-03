def test_upload_csv(client, sample_csv_bytes):
    response = client.post(
        "/upload",
        files={"file": ("sample_data.csv", sample_csv_bytes, "text/csv")},
    )

    assert response.status_code == 200, response.text
    dataset = response.json()
    assert dataset["rows"] == 6
    assert dataset["columns"] == 2
    assert type(dataset["id"]) is int
    assert dataset["id"] > 0


def test_process_and_retrieve(
    client, uploaded_dataset_id, processing_body
):
    response = client.post(
        f"/datasets/{uploaded_dataset_id}/process",
        json=processing_body,
    )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["validation_rows_removed"] == 1
    assert report["cleaning_report"]["rows_before"] == 5
    assert report["cleaning_report"]["rows_after"] == 3

    response = client.get(f"/datasets/{uploaded_dataset_id}")

    assert response.status_code == 200, response.text
    dataset = response.json()
    assert dataset["total_rows"] == 3
    assert sorted(dataset["data"], key=lambda row: row["student_id"]) == [
        {"student_id": 1, "score": 80},
        {"student_id": 2, "score": 90},
        {"student_id": 5, "score": 85},
    ]


def test_retrieve_missing_dataset(client):
    response = client.get("/datasets/999")

    assert response.status_code == 404, response.text
