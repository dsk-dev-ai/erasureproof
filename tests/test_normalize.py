from __future__ import annotations

import pytest

from erasureproof.core.normalize import (
    ACCESS,
    CORRECTION,
    DELETE,
    EXPORT,
    OPT_OUT,
    classify_request,
)


@pytest.mark.parametrize(
    "text",
    [
        "Please delete my account and all of my data.",
        "I want to exercise my right to be forgotten.",
        "Erase everything you hold about me.",
        "Quiero eliminar mi cuenta y todos mis datos.",
        "Merci de supprimer mon compte.",
        "Bitte löschen Sie mein Konto.",
        "Por favor, apague meus dados.",
        "Per favore, cancellare il mio account.",
        "Close my account.",
    ],
)
def test_deletion_requests_are_authorized(text: str) -> None:
    intent = classify_request(text)
    assert intent.is_deletion
    assert intent.category == DELETE


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Please send me a copy of my data.", EXPORT),
        ("I want to export my data.", EXPORT),
        ("Show me what data you have about me.", ACCESS),
        ("I need to correct my email address.", CORRECTION),
        ("Please unsubscribe me from marketing emails.", OPT_OUT),
        ("Necesito una copia de mis datos.", EXPORT),
        ("Je voudrais accéder à mes données.", ACCESS),
    ],
)
def test_non_deletion_requests_are_not_applicable(text: str, category: str) -> None:
    intent = classify_request(text)
    assert not intent.is_deletion
    assert intent.category == category


@pytest.mark.parametrize(
    "text",
    [
        "Please do not delete my account.",
        "Don't erase my data.",
        "I do not want to delete my account.",
        "No eliminar mi cuenta.",
        "Ne supprimez pas mon compte.",
        "Bitte nicht löschen.",
    ],
)
def test_negated_deletion_is_not_authorized(text: str) -> None:
    assert not classify_request(text).is_deletion


def test_empty_and_ambiguous_text() -> None:
    assert not classify_request("").is_deletion
    assert not classify_request("Hello, I have a question about my order.").is_deletion
