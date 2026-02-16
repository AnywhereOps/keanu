"""attune: three-key attunement (R/Y/B). pure ash."""

from keanu.abilities import Ability, ability


@ability
class ScanAbility(Ability):

    name = "attune"
    description = "Three-key attunement: red, yellow, blue"
    keywords = ["scan", "helix", "color", "mood", "three lens", "primary", "read", "attune"]
    cast_line = "attune opens the three keys..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if "helix" in p or "three lens" in p:
            return True, 0.9

        if "scan" in p and any(w in p for w in ["red", "yellow", "blue", "color", "mood"]):
            return True, 0.8

        # need a file path to actually scan
        if context and context.get("file_path") and "scan" in p:
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.abilities.seeing.scan.helix import run as helix_run

        file_path = None
        if context:
            file_path = context.get("file_path")

        if not file_path:
            return {
                "success": False,
                "result": "No file path provided for scanning.",
                "data": {},
            }

        try:
            report = helix_run(file_path, output_json=False)
            return {
                "success": True,
                "result": f"Scanned {file_path}",
                "data": {"file": file_path},
            }
        except Exception as e:
            return {
                "success": False,
                "result": f"Scan failed: {e}",
                "data": {},
            }
