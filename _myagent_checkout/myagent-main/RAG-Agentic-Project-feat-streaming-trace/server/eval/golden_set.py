"""The golden task set, mirrored from docs/eval.md as structured data so
run_eval.py can iterate over it. Keep this in sync with the table there by
hand — it's small enough that duplicating it isn't worth a markdown parser.

ids 1-9 are eval.md's "Our task set" (Guardian sales office / regulator
contacts). ids 10-18 are eval.md's "Task set 2" (COBRA continuation &
special Medicare rule), same source document, different section.
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
    {
        "id": 10,
        "goal": "Under the special Medicare rule, how long can a dependent's continuation period last?",
        "expected": (
            "The longer of: (a) 18 months (29 months if disability extension) from "
            "termination/reduction of work hours; or (b) 36 months from the date of "
            "the employee's earlier Medicare entitlement"
        ),
        "should_succeed": True,
    },
    {
        "id": 11,
        "goal": "When does the special Medicare rule not apply?",
        "expected": "When Medicare entitlement occurs more than 18 months before termination of employment or reduction of work hours",
        "should_succeed": True,
    },
    {
        "id": 12,
        "goal": "What events must a qualified continuee notify the employer about in writing?",
        "expected": (
            "(a) legal divorce/separation; (b) loss of dependent eligibility of an insured "
            "dependent child; (c) a second qualifying event after already on 18- or "
            "29-month continuation; (d) SSA disability determination during the first "
            "60 days of 18-month continuation; (e) SSA determination that the person is "
            "no longer disabled"
        ),
        "should_succeed": True,
    },
    {
        "id": 13,
        "goal": "How long does a qualified continuee have to give notice of a qualifying event?",
        "expected": "60 days",
        "should_succeed": True,
    },
    {
        "id": 14,
        "goal": "The 60-day notice deadline for a qualifying event starts from the latest of which dates?",
        "expected": (
            "(a) the date the qualifying event occurs; (b) the date the qualified "
            "continuee loses (or would lose) coverage; (c) the date the qualified "
            "continuee is informed of the notice responsibility and procedures"
        ),
        "should_succeed": True,
    },
    {
        "id": 15,
        "goal": "How long does a qualified continuee have to give notice of a disability determination?",
        "expected": (
            "60 days from the latest of: SSA determination date; qualifying event date; "
            "loss-of-coverage date; or date informed of notice procedures"
        ),
        "should_succeed": True,
    },
    {
        "id": 16,
        "goal": "What is the extra deadline for disability notice beyond the 60-day rule?",
        "expected": "It must be given before the end of the first 18 months of continuation coverage",
        "should_succeed": True,
    },
    {
        "id": 17,
        "goal": "Am I still eligible for COBRA continuation under the special Medicare rule?",
        "expected": "Decline — needs the person's employment/Medicare dates; not answerable from the booklet alone",
        "should_succeed": False,
    },
    {
        "id": 18,
        "goal": "Submit the written notice to my employer for me",
        "expected": "Decline — no submit/notify tool; agent should explain requirements only",
        "should_succeed": False,
    },
]
