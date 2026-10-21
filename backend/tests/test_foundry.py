import unittest
from types import SimpleNamespace

from app.foundry import _citations, _tool_result, create_agent_definition


class FoundryTests(unittest.TestCase):
    def test_agent_definition_attaches_read_only_station_tools_and_iq_mcp(self):
        definition = create_agent_definition(
            "asset-health-model",
            "https://example.test/knowledge/mcp",
            "asset-health-connection",
            ["read_knowledge"],
        ).as_dict()
        tools = definition["tools"]
        function_names = {tool["name"] for tool in tools if tool["type"] == "function"}
        self.assertEqual(
            function_names,
            {"list_station_health", "get_station_history", "get_maintenance_records"},
        )
        mcp = next(tool for tool in tools if tool["type"] == "mcp")
        self.assertEqual(mcp["server_url"], "https://example.test/knowledge/mcp")
        self.assertEqual(mcp["project_connection_id"], "asset-health-connection")
        self.assertEqual(mcp["require_approval"], "never")
        self.assertEqual(mcp["allowed_tools"], ["read_knowledge"])

    def test_agent_requires_an_explicit_knowledge_tool_allow_list(self):
        with self.assertRaises(ValueError):
            create_agent_definition("model", "https://example.test/mcp", "connection", [])

    def test_read_only_tools_are_station_scoped_and_bounded(self):
        result = _tool_result("get_station_history", {"station_id": "SE-001", "days": 31})
        self.assertIn("error", result)
        result = _tool_result("get_station_history", {"station_id": "SE-001", "days": 4})
        self.assertEqual(len(result["history"]), 4)
        self.assertEqual(result["data_classification"], "MOCK")
        self.assertIn("error", _tool_result("get_maintenance_records", {"station_id": "SE-999"}))

    def test_only_actual_url_and_file_citations_are_returned(self):
        annotations = [
            SimpleNamespace(type="url_citation", url="https://example.test/doc", title="Reference", text="Excerpt"),
            SimpleNamespace(type="url_citation", url="javascript:alert(1)", title="Unsafe", text=""),
            SimpleNamespace(type="unsupported", url="https://example.test/fake", title="Ignore", text=""),
        ]
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[SimpleNamespace(annotations=annotations)],
                )
            ]
        )
        citations = _citations(response)
        self.assertEqual(citations, [{"title": "Reference", "url": "https://example.test/doc", "excerpt": "Excerpt"}])


if __name__ == "__main__":
    unittest.main()
