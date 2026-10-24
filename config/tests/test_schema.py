import pytest


@pytest.mark.django_db
def test_openapi_schema_is_available_to_anonymous_user(client):
    response = client.get("/schema/", HTTP_ACCEPT="application/json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "DigiShop API"
    assert schema["info"]["version"] == "1.0.0"
    assert "/products/api/v1/products/" in schema["paths"]
    assert "/products/api/v1/categories/" in schema["paths"]


def test_swagger_ui_is_available_to_anonymous_user(client):
    response = client.get("/docs/")

    assert response.status_code == 200
    assert "DigiShop API" in response.content.decode()
