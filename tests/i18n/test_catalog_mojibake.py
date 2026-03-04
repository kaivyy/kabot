from kabot.i18n import catalog as catalog_module


def test_tr_falls_back_to_english_when_locale_template_is_mojibake(monkeypatch):
    key = "runtime.status.queued"
    monkeypatch.setitem(catalog_module._CATALOG, "xx", {key: "Ã¢â‚¬â€ ÃƒÂ© broken"})

    translated = catalog_module.tr(key, locale="xx")

    assert translated == catalog_module._CATALOG["en"][key]
