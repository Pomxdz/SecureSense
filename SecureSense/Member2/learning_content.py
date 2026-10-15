"""Category-specific original lessons and assessments; no external quiz results imported."""

CONTENT = {
    "Financial Fraud": (
        [
            "An invoice or payroll request may impersonate a supplier or manager. A familiar name, logo or existing email thread is not proof of identity.",
            "Treat changed bank details, unusual urgency and requests to bypass approvals as warning signs. Compare the request with the approved purchase or payroll record.",
            "Call the supplier using a number already held in trusted records. Do not use a phone number or link supplied in the suspicious message.",
            "Follow dual approval and payment-change procedures. If you already acted, stop further payment and report immediately so Finance and InfoSec can respond.",
        ],
        [
            (
                "An invoice changes bank details. What is the safest next step?",
                [
                    "Pay before the deadline",
                    "Verify using an existing trusted supplier contact",
                    "Reply to the same email only",
                ],
                1,
            ),
            (
                "The chief executive asks for an urgent transfer outside policy. What should you do?",
                [
                    "Follow independent verification and approval",
                    "Bypass approval because of seniority",
                    "Send part of the amount first",
                ],
                0,
            ),
            (
                "Which contact is suitable for verification?",
                [
                    "The number in the new invoice",
                    "The address in the email signature",
                    "A number already in approved supplier records",
                ],
                2,
            ),
            (
                "You already approved a suspicious transfer. What next?",
                [
                    "Wait to see whether it clears",
                    "Report promptly to Finance and InfoSec and stop further action",
                    "Delete the message",
                ],
                1,
            ),
            (
                "What supports a safe payment-change decision?",
                [
                    "A familiar logo",
                    "Urgency alone",
                    "Verified identity plus the required approval trail",
                ],
                2,
            ),
        ],
    ),
    "Credential Harvesting": (
        [
            "A sign-in link may imitate a trusted service to obtain credentials. This simulation uses a test email only; never enter a real password or one-time code.",
            "Inspect the full destination domain. A padlock indicates encrypted transport, not that the organization or request is legitimate.",
            "Open the service through your saved bookmark or independently known address. Verify the request through the official support channel.",
            "If you entered information, stop and report what happened. Follow InfoSec instructions for account protection; reporting remains useful after interaction.",
        ],
        [
            (
                "A message sends you to an unexpected login form. What should you do?",
                [
                    "Enter a password to test it",
                    "Open the official service independently and verify",
                    "Trust its logo",
                ],
                1,
            ),
            (
                "What does a padlock alone establish?",
                [
                    "Encrypted transport, not legitimacy",
                    "The sender is trusted",
                    "The request is approved",
                ],
                0,
            ),
            (
                "A support message asks for a one-time code. What is appropriate?",
                [
                    "Send it if urgent",
                    "Send it to the manager",
                    "Do not share it; verify through official support",
                ],
                2,
            ),
            (
                "You entered information on a suspicious form. What next?",
                ["Hide the mistake", "Stop and report promptly", "Try again"],
                1,
            ),
            (
                "Which destination check is useful?",
                [
                    "The page color",
                    "The full domain against an independently known address",
                    "The length of the email",
                ],
                1,
            ),
        ],
    ),
    "Urgent Extortion": (
        [
            "Threatening messages use fear, embarrassment or deadlines to rush decisions. A threat does not establish that the sender has the claimed access or authority.",
            "Pause before paying, opening attachments or sharing information. Keep the message as evidence and avoid arguing with the sender.",
            "Verify through a trusted independent channel and report to InfoSec. Follow the organization’s incident procedure rather than an attacker’s deadline.",
            "If there is an immediate physical safety concern, use the appropriate emergency channel. For this simulation, record the fictional message and report the suspicious demand.",
        ],
        [
            (
                "A message threatens consequences unless you act immediately. What next?",
                [
                    "Pause and verify independently",
                    "Pay immediately",
                    "Send private information",
                ],
                0,
            ),
            (
                "What should you do with the suspicious message?",
                [
                    "Delete all evidence",
                    "Preserve it and report through the approved channel",
                    "Forward it to everyone",
                ],
                1,
            ),
            (
                "Does a detailed threat prove the sender has access?",
                [
                    "Always",
                    "Only if it names you",
                    "No; verify the claim independently",
                ],
                2,
            ),
            (
                "Which deadline governs your response?",
                [
                    "The attacker deadline",
                    "Your incident procedure and verified safety needs",
                    "Any deadline in bold",
                ],
                1,
            ),
            (
                "You already responded to the threat. What should you do?",
                [
                    "Stop and report promptly",
                    "Continue negotiating secretly",
                    "Hide the interaction",
                ],
                0,
            ),
        ],
    ),
    "Social Engineering": (
        [
            "Attackers may impersonate a colleague, manager or support technician and use authority, familiarity or rewards to persuade you.",
            "Notice requests to bypass procedures, share sensitive information, install tools or keep a request secret. A familiar display name is easy to imitate.",
            "Verify identity through an independently known channel. Apply the same approval and access rules even if the sender appears senior.",
            "If you interacted, stop and report. Explain the observed request and actions without guessing the sender’s motives.",
        ],
        [
            (
                "A manager asks you to bypass a normal process. What next?",
                [
                    "Comply because of their title",
                    "Verify independently and follow the process",
                    "Ask only the same sender",
                ],
                1,
            ),
            (
                "A familiar display name proves identity. Is that correct?",
                ["Yes", "Only during work hours", "No; names can be impersonated"],
                2,
            ),
            (
                "A support caller asks for your password. What should you do?",
                [
                    "Do not share it; verify support independently",
                    "Read it aloud",
                    "Send it by email",
                ],
                0,
            ),
            (
                "A reward requires sensitive information. What next?",
                [
                    "Act before the offer expires",
                    "Verify the offer through an official channel",
                    "Share a colleague’s details",
                ],
                1,
            ),
            (
                "After a suspicious interaction, what helps InfoSec?",
                [
                    "Hide it",
                    "Delete evidence",
                    "Report the request and your actions promptly",
                ],
                2,
            ),
        ],
    ),
    "Malware Delivery": (
        [
            "Unexpected documents, archives or update links can lead to unsafe software. This assignment uses harmless examples and does not deliver malware.",
            "Be cautious with instructions to enable macros, run installers or disable protection. A familiar sender does not prove an attachment is expected.",
            "Verify the file through a trusted channel and use approved software or update tools. Do not run an unexpected file to find out whether it is malicious.",
            "If you opened something suspicious, stop and contact InfoSec. Follow their containment instructions rather than improvising fixes.",
        ],
        [
            (
                "An attachment asks you to enable macros. What next?",
                [
                    "Enable them to preview",
                    "Verify independently and use the approved process",
                    "Disable antivirus",
                ],
                1,
            ),
            (
                "Where should software updates come from?",
                ["Approved update channels", "Any email link", "An unknown file share"],
                0,
            ),
            (
                "A familiar sender unexpectedly sends an installer. What next?",
                [
                    "Run it",
                    "Forward it widely",
                    "Confirm through an independently known channel",
                ],
                2,
            ),
            (
                "You already opened a suspicious file. What should you do?",
                [
                    "Hide the action",
                    "Stop and contact InfoSec promptly",
                    "Run it again",
                ],
                1,
            ),
            (
                "How does this assignment simulate malware delivery?",
                [
                    "With harmless examples and safe interaction telemetry",
                    "By deploying live malware",
                    "By disabling protection",
                ],
                0,
            ),
        ],
    ),
    "General": (
        [
            "Check whether a message is expected and whether the sender and destination match trusted records.",
            "Pause when urgency, authority, fear or rewards pressure you to act.",
            "Verify requests through an independently known channel. Never share passwords or one-time codes.",
            "Report suspicious messages promptly, including after interaction. Preserve useful evidence.",
        ],
        [
            (
                "A request is unexpected. What next?",
                ["Act quickly", "Verify independently", "Trust the logo"],
                1,
            ),
            (
                "Which contact should you use?",
                [
                    "The suspicious email’s number",
                    "An independently known channel",
                    "A link in the message",
                ],
                1,
            ),
            (
                "Should you share a one-time code?",
                ["Yes if urgent", "Yes with any manager", "No"],
                2,
            ),
            (
                "After interaction, what helps?",
                ["Prompt reporting", "Deleting evidence", "Keeping it secret"],
                0,
            ),
            (
                "What does no recorded interaction prove?",
                [
                    "The user is safe",
                    "The user is unsafe",
                    "Neither; evidence is incomplete",
                ],
                2,
            ),
        ],
    ),
}
