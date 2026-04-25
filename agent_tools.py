AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Получить баланс пользователя",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_confirmation",
            "description": "Запросить подтверждение перед платежом. ОБЯЗАТЕЛЬНО перед любым списанием.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "amount": {"type": "number"},
                    "details": {"type": "string"}
                },
                "required": ["action", "amount", "details"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "private_transfer",
            "description": "Отправить USDC приватно",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "amount": {"type": "number"},
                    "memo": {"type": "string"}
                },
                "required": ["recipient", "amount"]
            }
        }
    }
]