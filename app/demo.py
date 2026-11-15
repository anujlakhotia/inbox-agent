from datetime import datetime, timedelta

_NOW = datetime.utcnow()


def _e(i, sender, addr, subject, body, hours_ago):
    return {
        "id": f"demo{i}",
        "thread_id": f"demo{i}",
        "sender": sender,
        "sender_email": addr,
        "subject": subject,
        "date": (_NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S"),
        "snippet": body[:120],
        "body": body,
    }


EMAILS = [
    _e(1, "The Agent Weekly", "news@agentweekly.example", "How agent frameworks are converging on tool use",
       "This week: AI agent frameworks are converging on a small set of patterns. Tool use, memory and evaluation loops matter most. Startups building agents should focus on reliability first.", 3),
    _e(2, "Stratechery Lite", "hello@strat.example", "Pricing strategy for AI products",
       "Business strategy: usage-based pricing is replacing seats for AI products. Founders should model gross margin per task. Product teams need clear value metrics.", 8),
    _e(3, "Habit Notes", "habits@notes.example", "The sleep habit that changed my productivity",
       "A habit and mindset essay on sleep: consistent wake times beat total hours. Health and learning both improve. A small daily routine compounds.", 12),
    _e(4, "Priya (Accountant)", "priya@firm.example", "Action required: invoice approval by Friday",
       "Hi, please reply to approve the invoice. Deadline is Friday. Payment due soon.", 5),
    _e(5, "Shoe Store", "deals@shoes.example", "50% off everything this weekend", "Huge sale on shoes. Buy now!", 2),
]
