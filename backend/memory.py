import time

MAX_MESSAGES = 10
RECENT_MESSAGES = 5


class ConversationMemory:
    def __init__(self):
        self.messages = []
        self.summary = ""

    def add_message(self, role, content):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def should_summarize(self):
        return len(self.messages) > MAX_MESSAGES

    def summarize(self, summarizer_fn):
        """
        summarizer_fn = function that calls LLM
        """

        old_messages = self.messages[:-RECENT_MESSAGES]

        if not old_messages:
            return

        text = "\n".join([m["content"] for m in old_messages])

        new_summary = summarizer_fn(text)

        if self.summary:
            self.summary += "\n" + new_summary
        else:
            self.summary = new_summary

        # keep only recent messages
        self.messages = self.messages[-RECENT_MESSAGES:]

    def get_context(self):
        context = []

        if self.summary:
            context.append({
                "role": "system",
                "content": f"Conversation summary:\n{self.summary}"
            })

        context.extend(self.messages)

        return context
