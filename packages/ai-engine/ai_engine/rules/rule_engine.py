"""
风险规则引擎
"""
from datetime import datetime, timezone
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Risk:
    """风险信息"""
    type: str
    level: RiskLevel
    message: str
    detection_ids: List[int]  # 关联的检测ID
    metadata: Dict[str, Any]

class RuleEngine:
    """风险规则引擎"""

    def __init__(self, rules_dir: Path):
        self.rules_dir = Path(rules_dir)
        self.rules: List[Dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self):
        """加载规则文件"""
        self.rules.clear()

        # 加载YAML规则文件
        for rule_file in self.rules_dir.glob("*.yaml"):
            try:
                with open(rule_file, 'r', encoding='utf-8') as f:
                    rule_data = yaml.safe_load(f)

                if "rules" in rule_data:
                    for rule in rule_data["rules"]:
                        rule["source"] = rule_file.name
                        self.rules.append(rule)

                print(f"📋 加载规则文件: {rule_file.name}, {len(rule_data.get('rules', []))} 条规则")

            except Exception as e:
                print(f"❌ 加载规则文件失败 {rule_file}: {e}")

        # 加载Python规则模块
        for rule_file in self.rules_dir.glob("*.py"):
            if rule_file.name == "__init__.py":
                continue

            try:
                module_name = f"ai_engine.rules.{rule_file.stem}"
                # 动态导入
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, rule_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 检查模块是否有规则
                if hasattr(module, "get_rules"):
                    rules = module.get_rules()
                    for rule in rules:
                        rule["source"] = rule_file.name
                        self.rules.append(rule)

                    print(f"📋 加载Python规则: {rule_file.name}, {len(rules)} 条规则")

            except Exception as e:
                print(f"❌ 加载Python规则失败 {rule_file}: {e}")

        # 如果没有规则文件，加载默认规则
        if not self.rules:
            self._load_default_rules()

    def _load_default_rules(self):
        """加载默认风险规则"""
        print("📋 加载默认风险规则")

        default_rules = [
            {
                "name": "missing_helmet",
                "condition": "person_detected and (class_id == 7)",
                "level": "high",
                "message": "未佩戴安全帽",
                "description": "检测到人员但未佩戴安全帽"
            },
            {
                "name": "missing_vest",
                "condition": "person_detected and vest_bbox is None",
                "level": "medium",
                "message": "未穿反光衣",
                "description": "检测到人员但未穿反光衣"
            },
            {
                "name": "no_ppe_at_all",
                "condition": "class_id == 5",
                "level": "critical",
                "message": "完全无防护，立即处理",
                "description": "检测到完全无防护人员"
            },
            {
                "name": "missing_gloves",
                "condition": "person_detected and gloves_bbox is None",
                "level": "low",
                "message": "未戴手套",
                "description": "检测到人员但未戴手套"
            },
            {
                "name": "missing_boots",
                "condition": "person_detected and boots_bbox is None",
                "level": "low",
                "message": "未穿安全鞋",
                "description": "检测到人员但未穿安全鞋"
            }
        ]

        for rule in default_rules:
            rule["source"] = "default"
            self.rules.append(rule)

    def evaluate_detections(self, detections: List[Dict[str, Any]]) -> List[Risk]:
        """
        评估检测结果，应用风险规则

        Args:
            detections: 检测结果列表

        Returns:
            风险列表
        """
        risks = []

        # 准备评估上下文
        context = self._build_evaluation_context(detections)

        # 应用每条规则
        for rule in self.rules:
            try:
                risk = self._evaluate_rule(rule, context, detections)
                if risk:
                    risks.append(risk)
            except Exception as e:
                print(f"❌ 规则评估失败 {rule.get('name')}: {e}")

        return risks

    def _build_evaluation_context(self, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建规则评估上下文"""
        context = {
            "person_detected": False,
            "person_bboxes": [],
            "helmet_bboxes": [],
            "no_helmet_bboxes": [],
            "vest_bboxes": [],
            "gloves_bboxes": [],
            "boots_bboxes": [],
            "goggles_bboxes": [],
            "none_bboxes": []
        }

        for det in detections:
            class_name = det.get("class", "")

            if class_name == "Person":
                context["person_detected"] = True
                context["person_bboxes"].append(det.get("bbox"))
            elif class_name == "helmet":
                context["helmet_bboxes"].append(det.get("bbox"))
            elif class_name == "no_helmet":
                context["no_helmet_bboxes"].append(det.get("bbox"))
            elif class_name == "vest":
                context["vest_bboxes"].append(det.get("bbox"))
            elif class_name == "gloves":
                context["gloves_bboxes"].append(det.get("bbox"))
            elif class_name == "boots":
                context["boots_bboxes"].append(det.get("bbox"))
            elif class_name == "goggles":
                context["goggles_bboxes"].append(det.get("bbox"))
            elif class_name == "none":
                context["none_bboxes"].append(det.get("bbox"))

        return context

    def _evaluate_rule(self, rule: Dict[str, Any], context: Dict[str, Any],
                      detections: List[Dict[str, Any]]) -> Optional[Risk]:
        """评估单条规则"""
        condition = rule.get("condition", "")

        # 简单的规则评估逻辑
        # 在实际应用中，应该使用更复杂的表达式求值器
        if condition == "person_detected and (class_id == 7)":
            # 未戴安全帽规则
            if context["person_detected"] and context["no_helmet_bboxes"]:
                # 找到关联的检测
                detection_ids = []
                for i, det in enumerate(detections):
                    if det.get("class") == "no_helmet":
                        detection_ids.append(i)

                if detection_ids:
                    return Risk(
                        type=rule["name"],
                        level=RiskLevel(rule["level"]),
                        message=rule["message"],
                        detection_ids=detection_ids,
                        metadata={"rule_source": rule["source"]}
                    )

        elif condition == "person_detected and vest_bbox is None":
            # 未穿反光衣规则（隐式）
            if context["person_detected"] and not context["vest_bboxes"]:
                # 找到所有人员检测
                detection_ids = []
                for i, det in enumerate(detections):
                    if det.get("class") == "Person":
                        detection_ids.append(i)

                if detection_ids:
                    return Risk(
                        type=rule["name"],
                        level=RiskLevel(rule["level"]),
                        message=rule["message"],
                        detection_ids=detection_ids,
                        metadata={
                            "rule_source": rule["source"],
                            "implicit": True
                        }
                    )

        elif condition == "class_id == 5":
            # 完全无防护规则
            if context["none_bboxes"]:
                detection_ids = []
                for i, det in enumerate(detections):
                    if det.get("class") == "none":
                        detection_ids.append(i)

                if detection_ids:
                    return Risk(
                        type=rule["name"],
                        level=RiskLevel(rule["level"]),
                        message=rule["message"],
                        detection_ids=detection_ids,
                        metadata={"rule_source": rule["source"]}
                    )

        # 可以添加更多规则条件...

        return None

    def add_rule(self, rule: Dict[str, Any]):
        """添加规则"""
        rule["source"] = "dynamic"
        self.rules.append(rule)

    def remove_rule(self, rule_name: str):
        """移除规则"""
        self.rules = [r for r in self.rules if r.get("name") != rule_name]

    def get_rules(self) -> List[Dict[str, Any]]:
        """获取所有规则"""
        return self.rules.copy()

    def reload_rules(self):
        """重新加载规则"""
        self._load_rules()

    def export_rules(self, output_path: Path):
        """导出规则到YAML文件"""
        export_data = {
            "rules": self.rules,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_rules": len(self.rules)
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(export_data, f, allow_unicode=True, default_flow_style=False)

        print(f"💾 规则导出到: {output_path}")