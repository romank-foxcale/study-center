import copy

from mentor_core import graph as g


def test_fixture_graph_is_valid(graph_yaml):
    result = g.validate(g.parse(graph_yaml))
    assert result["ok"], result["errors"]
    assert result["stats"]["nodes"] == 7
    assert result["stats"]["encompasses_edges"] == 2
    assert result["stats"]["depth"] == 5


def test_cycle_is_an_error(graph_yaml):
    doc = g.parse(graph_yaml)
    doc["edges"].append({"kind": "prereq", "from": "pca.core", "to": "vec.basics"})
    result = g.validate(doc)
    assert not result["ok"]
    assert any("cycle" in e for e in result["errors"])


def test_unknown_endpoint_and_bad_weight(graph_yaml):
    doc = g.parse(graph_yaml)
    doc["edges"].append({"kind": "prereq", "from": "nope", "to": "vec.dot"})
    doc["edges"].append({"kind": "encompasses", "from": "eig.def", "to": "vec.dot", "weight": 1.5})
    errors = g.validate(doc)["errors"]
    assert any("unknown node" in e for e in errors)
    assert any("weight" in e for e in errors)


def test_schema_errors(graph_yaml):
    doc = g.parse(graph_yaml)
    bad = copy.deepcopy(doc["nodes"][0])
    bad.update(id="Bad Id", type="vibes", tier="x", bloom="memorize")
    doc["nodes"].append(bad)
    doc["nodes"].append({"id": "x.missing"})
    errors = g.validate(doc)["errors"]
    assert any("id must match" in e for e in errors)
    assert any("type must be" in e for e in errors)
    assert any("missing" in e for e in errors)


def test_warnings_for_sizing_and_direction(graph_yaml):
    doc = g.parse(graph_yaml)
    doc["nodes"][0]["minutes"] = 90
    doc["edges"].append({"kind": "encompasses", "from": "vec.basics", "to": "pca.core", "weight": 0.3})
    result = g.validate(doc)
    assert result["ok"]
    assert any("splitting" in w for w in result["warnings"])
    assert any("not downstream" in w for w in result["warnings"])


def test_graph_view_and_mermaid(graph_yaml):
    doc = g.parse(graph_yaml)
    view = g.Graph(doc["nodes"], doc["edges"], doc["capabilities"])
    assert view.prereqs("mat.mult") == ["mat.basics", "vec.dot"]
    assert view.encompassed_by("mat.mult") == [("vec.dot", 0.7)]
    assert view.topo()[0] in ("stats.cov", "vec.basics")
    mermaid = g.to_mermaid(view, {"vec.basics": "mastered"})
    assert mermaid.startswith("flowchart TD")
    assert "classDef mastered" in mermaid
