import pytest

from contracts import ContractError, validate_knowledge_item, validate_training_content


def test_knowledge_contract_requires_traceable_location():
    with pytest.raises(ContractError, match="来源定位"):
        validate_knowledge_item(
            {"知识ID": "K1", "内容": "内容", "来源": "来源", "主题": ["主题"]}
        )


@pytest.mark.parametrize("resource_type", ["教程", "阶梯项目"])
def test_training_contract_rejects_old_resource_type(resource_type):
    with pytest.raises(ContractError, match="不支持的资源类型"):
        validate_training_content(
            {
                "类型": resource_type,
                "标题": "标题",
                "正文": "正文",
                "引用来源": [],
                "引用知识ID": [],
            }
        )
