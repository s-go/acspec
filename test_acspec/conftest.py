# -*- coding: utf-8 -*-
import pytest


@pytest.fixture()
def model_specs(request):
    return {
        "blog": {
            "posts": {
                "type": {
                    "list": {
                        "model": "post"
                    }
                }
            }
        },
        "author": {
            "id": {
                "type": {
                    "simple": "string"
                }
            },
            "first_name": {
                "type": {
                    "simple": "string"
                }
            },
            "last_name": {
                "type": {
                    "simple": "string"
                }
            }
        },
        "post": {
            "id": {
                "type": {
                    "simple": "string"
                }
            },
            "title": {
                "type": {
                    "simple": "string"
                }
            },
            "text": {
                "type": {
                    "simple": "string"
                }
            },
            "tags": {
                "type": {
                    "list": {
                        "simple": "string"
                    }
                },
                "serialize_when_none": False,
            },
            "author": {
                "type": {
                    "model": "author"
                },
                "serialize_when_none": False,
                "required": True
            }
        }
    }


@pytest.fixture()
def acspec(request):
    from acspec.base import Acspec
    return Acspec(model_specs(request))


@pytest.fixture()
def author_data(request):
    return {
        "id": "1",
        "first_name": "John",
        "last_name": "Smith"
    }


@pytest.fixture()
def post_data(request):
    return {
        "id": "123",
        "title": "TestPost",
        "text": "TestText",
        "tags": ["test", "blog"],
        "author": author_data(request)
    }
