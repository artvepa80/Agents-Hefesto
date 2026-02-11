from hefesto.analyzers.cloud.graph.graph_builder import CloudFormationGraphBuilder


def test_graph_builder_extracts_refs_and_getatt():
    template = {
        "Resources": {
            "A": {"Type": "AWS::S3::Bucket", "Properties": {}},
            "B": {"Type": "AWS::Lambda::Function", "Properties": {"Role": {"Ref": "C"}}},
            "C": {"Type": "AWS::IAM::Role", "Properties": {}},
            "D": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Env": {"Fn::GetAtt": ["A", "Arn"]}},
            },
        }
    }

    nodes, edges = CloudFormationGraphBuilder().build(template)
    assert nodes == {"A", "B", "C", "D"}
    assert any(e.src == "B" and e.dst == "C" and e.kind == "Ref" for e in edges)
    assert any(e.src == "D" and e.dst == "A" and e.kind == "GetAtt" for e in edges)
