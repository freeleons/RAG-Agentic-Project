"""The golden task set, mirrored from docs/eval.md as structured data so
run_eval.py can iterate over it. Keep this in sync with the table there by
hand — it's small enough that duplicating it isn't worth a markdown parser.
"""

GOLDEN_SET = [
    {
        "id": 1,
        "goal": "Guardian sales office phone number?",
        "expected": "(301) 957-7320",
        "should_succeed": True,
    },
    {
        "id": 2,
        "goal": "Guardian sales office fax?",
        "expected": "(301) 957-7339",
        "should_succeed": True,
    },
    {
        "id": 3,
        "goal": "Full mailing address of The Guardian Sales Office?",
        "expected": "Maple Lawn Office Three, 8161 Maple Lawn Boulevard, Suite 100, Maple Lawn, Maryland 20759",
        "should_succeed": True,
    },
    {
        "id": 4,
        "goal": "If I cannot get satisfaction from the agent or company, who do I contact in Virginia?",
        "expected": "Virginia State Corporation Commission, Bureau of Insurance, P.O. Box 1157, Richmond, VA 23218; (800) 552-7945",
        "should_succeed": True,
    },
    {
        "id": 5,
        "goal": "Complaint about availability/quality of health care services — who to contact?",
        "expected": (
            "Office of Licensure and Certification, Virginia Department of Health, "
            "9960 Maryland Drive - Suite 401, Richmond, VA 23233-1463; Richmond metro "
            "(804) 367-2106 or (800) 955-1819; email mchip@vdh.virginia.gov"
        ),
        "should_succeed": True,
    },
    {
        "id": 6,
        "goal": "Will I be penalized for filing a complaint?",
        "expected": "No — you will not be penalized for exercising these rights.",
        "should_succeed": True,
    },
    {
        "id": 7,
        "goal": "When contacting the agent, company, or Bureau of Insurance, what should I have available?",
        "expected": "Your policy number",
        "should_succeed": True,
    },
    {
        "id": 8,
        "goal": "What is my Guardian policy number?",
        "expected": "Decline / not in KB — policy number is personal, not in the booklet",
        "should_succeed": False,
    },
    {
        "id": 9,
        "goal": "Call the Bureau of Insurance for me and file the complaint",
        "expected": "Decline — no phone/email-send tool; agent should give the number, not act",
        "should_succeed": False,
    },
]
