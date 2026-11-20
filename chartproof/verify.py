"""Compile bounded English claims, then replay them against versioned evidence."""
from dataclasses import dataclass, asdict
from decimal import Decimal
import re
from .language import classify

YEAR = r"(?:19|20)\d{2}"
NUMBER = r"\d{1,5}(?:\.\d{1,4})?"
COMPARE = {"at least": ">=", "no less than": ">=", "at most": "<=", "no more than": "<=",
           "over": ">", "more than": ">", "above": ">", "greater than": ">",
           "under": "<", "less than": "<", "below": "<", "fewer than": "<",
           "exactly": "=", "": "="}
NUMBER_CLAUSE = r"(?:(?P<compare>"+"|".join(x for x in COMPARE if x)+r")\s+)?(?P<target>"+NUMBER+r")\s*"
PERCENT = r"(?:%|percent(?:age)?|per cent)"
MOVES = {"increased": 1, "rose": 1, "grew": 1, "climbed": 1, "gained": 1, "went up": 1,
         "decreased": -1, "fell": -1, "dropped": -1, "declined": -1, "went down": -1}
OPERATORS = {"=": lambda a, b: a == b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
             ">": lambda a, b: a > b, "<": lambda a, b: a < b}
SUPPORTED = "Supported"
FALSE = "Contradicted"
UNKNOWN = "Insufficient evidence"


def clean(text):
    return " ".join(text.strip().lower().split())


def metric_key(text):
    return re.sub(r"^the\s+", "", clean(text))


def fmt(value):
    value = Decimal(str(value))
    return format(value, "f").rstrip("0").rstrip(".") if "." in format(value, "f") else str(value)


def display_num(value):
    return fmt(value.quantize(Decimal("0.0001")))


@dataclass(frozen=True)
class Check:
    text: str
    operation: str
    metric: str
    years: tuple
    compare: str
    target: str
    direction: int
    model_label: str
    model_score: float
    reason: str = ""


def compile_claim(text):
    sentence = clean(text).rstrip(".!?")
    label, score = classify(sentence)
    empty = Check(text, "other", "", (), "", "", 1, label, score,
                  "This sentence cannot be expressed as one supported percentage check. Specify the metric, year(s), operation and threshold.")
    metric = r"(?:the\s+)?(?P<metric>[a-z][a-z0-9 &'/-]{0,80}?)\s+"
    is_verb = r"(?:was|is|stood at|reached|measured|equalled|equaled)\s+"
    yearly = re.fullmatch(metric+is_verb+NUMBER_CLAUSE+PERCENT+r"\s+in\s+(?P<end>"+YEAR+")", sentence)
    if not yearly:
        yearly = re.fullmatch(r"in\s+(?P<end>"+YEAR+r"),?\s+"+metric +
                              is_verb+NUMBER_CLAUSE+PERCENT, sentence)
    if yearly:
        parts = yearly.groupdict()
        op, years, direction = "lookup", (parts["end"],), 1
    else:
        moved = r"(?P<move>"+"|".join(MOVES)+r")\s+(?:by\s+)?"
        unit = r"(?P<unit>percentage points?|points?|pp|"+PERCENT+r")"
        pair = (r"(?:from\s+(?P<a>"+YEAR+r")\s+to\s+(?P<b>"+YEAR+r")|between\s+(?P<c>"+YEAR +
                r")\s+and\s+(?P<d>"+YEAR+r")|relative to\s+(?P<e>"+YEAR+r")\s+in\s+(?P<f>"+YEAR+r"))")
        change = re.fullmatch(metric+moved+NUMBER_CLAUSE+unit+r"\s+"+pair, sentence)
        if not change:
            return empty
        parts = change.groupdict()
        years = (parts["a"] or parts["c"] or parts["e"], parts["b"] or parts["d"] or parts["f"])
        if parts["c"]:
            years = tuple(sorted(years))
        if years[0] == years[1]:
            return empty
        op = "points" if "point" in parts["unit"] or parts["unit"] == "pp" else "relative"
        direction = MOVES[parts["move"]]
    why = "" if label == op else "Language model and explicit units disagree. Rephrase the claim before accepting a verdict."
    return Check(text, op, metric_key(parts["metric"]), years, COMPARE[parts["compare"] or ""],
                 parts["target"], direction, label, score, why)


def verify(check, chart):
    rows = {row["year"]: Decimal(str(row["value"])) for row in chart["rows"]}
    evidence = [{"year": y, "value": fmt(rows[y])} for y in check.years if y in rows]

    def result(status, reason, formula="", correction=""):
        return {"status": status, "reason": reason, "evidence": evidence, "formula": formula, "correction": correction}
    if check.reason:
        return result(UNKNOWN, check.reason)
    if metric_key(chart["metric"]) != check.metric:
        return result(UNKNOWN, "The chart metric does not match the metric named in the claim.")
    missing = [y for y in check.years if y not in rows]
    if missing:
        return result(UNKNOWN, "Missing percentage for " + ", ".join(missing) + ".")
    new = rows[check.years[-1]]
    unit = "%"
    if check.operation == "lookup":
        actual = new
        formula = f"{check.years[0]} = {fmt(actual)}%"
        observed = f"{chart['metric']} was {fmt(actual)}% in {check.years[0]}."
    else:
        old = rows[check.years[0]]
        delta = new-old
        if check.operation == "points":
            actual = delta
            unit = " pp"
            formula = f"{fmt(new)}% − {fmt(old)}% = {display_num(delta)} pp"
        else:
            if old == 0:
                return result(UNKNOWN, "Relative change is undefined because the starting value is zero.")
            actual = 100*delta/old
            formula = f"({fmt(new)} − {fmt(old)}) / {fmt(old)} × 100 = {display_num(actual)}%"
        verb = "rose" if actual > 0 else "fell" if actual < 0 else "did not change"
        amount = (" by "+display_num(abs(actual)) +
                  (" percentage points" if unit == " pp" else "%")) if actual else ""
        observed = f"{chart['metric']} {verb}{amount} from {check.years[0]} to {check.years[1]}."
        actual *= check.direction
    verified = OPERATORS[check.compare](actual, Decimal(check.target))
    if check.operation != "lookup" and actual <= 0:
        verified = False
    return result(SUPPORTED if verified else FALSE, "The displayed values satisfy the claim." if verified else
                  "The displayed values do not satisfy the claim.", formula, "" if verified else observed)


def linked_claim(text, binding):
    if not isinstance(binding, dict):
        raise ValueError("Invalid reviewer binding.")
    op = binding.get("operation")
    years = binding.get("years")
    operator = binding.get("compare")
    target = str(binding.get("target", ""))
    metric = binding.get("metric")
    direction = binding.get("direction")
    if (op not in {"lookup", "points", "relative"} or operator not in OPERATORS or
        not isinstance(years, list) or len(years) != (1 if op == "lookup" else 2) or
        not all(isinstance(y, str) and re.fullmatch(YEAR, y) for y in years) or len(set(years)) != len(years) or
        type(direction) is not int or direction not in {-1, 1} or not re.fullmatch(NUMBER, target) or
            not isinstance(metric, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9 &'/–-]{0,79}", metric)):
        raise ValueError(
            "The reviewer binding needs valid years, metric, direction, operator and threshold.")
    label, score = classify(text)
    return Check(text, op, metric_key(metric), tuple(years), operator, target, direction, label, score)


def compare(text, original, revision, binding=None):
    check = compile_claim(text) if binding is None else linked_claim(text, binding)
    before, after = verify(check, original), verify(check, revision)
    if before["status"] == SUPPORTED and after["status"] == FALSE:
        transition = "Outdated claim"
    elif after["status"] == UNKNOWN:
        transition = "Needs evidence"
    elif before["status"] == FALSE and after["status"] == FALSE:
        transition = "Already contradicted"
    elif before["status"] != after["status"]:
        transition = "Verdict changed"
    else:
        transition = "Verdict retained"
    return {"claim": text, "binding_source": "Automatic" if binding is None else "Reviewer linked", "check": asdict(check), "before": before, "after": after, "transition": transition}
