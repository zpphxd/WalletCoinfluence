"""LLM-based signal analysis using open source models."""

import logging
import json
from typing import Dict, Any, Optional, List
import httpx

logger = logging.getLogger(__name__)


class LLMSignalAnalyzer:
    """Uses open-source LLM to analyze token signals and provide insights."""

    def __init__(
        self,
        api_url: str = "http://localhost:11434/api/generate",  # Ollama default
        model: str = "llama3.2:latest",  # or mistral, phi, etc.
    ):
        """Initialize LLM analyzer.

        Args:
            api_url: URL for LLM API (Ollama, LM Studio, etc.)
            model: Model name to use
        """
        self.api_url = api_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)

    async def analyze_token_signal(
        self,
        token_data: Dict[str, Any],
        wallet_data: List[Dict[str, Any]],
        historical_performance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze token buy signal using LLM.

        Args:
            token_data: Token metadata (price, liquidity, etc.)
            wallet_data: Wallet(s) that bought
            historical_performance: Past alert outcomes

        Returns:
            Analysis result with signal strength and reasoning
        """
        prompt = self._build_analysis_prompt(token_data, wallet_data, historical_performance)

        try:
            response = await self._query_llm(prompt)

            # Parse LLM response
            analysis = self._parse_llm_response(response)

            return {
                "signal_strength": analysis.get("signal_strength", 0),  # 0-100
                "confidence": analysis.get("confidence", 0),  # 0-100
                "reasoning": analysis.get("reasoning", ""),
                "red_flags": analysis.get("red_flags", []),
                "positive_signals": analysis.get("positive_signals", []),
                "recommendation": analysis.get("recommendation", "HOLD"),
                "risk_level": analysis.get("risk_level", "MEDIUM"),
            }

        except Exception as e:
            logger.error(f"LLM analysis error: {str(e)}")
            return {
                "signal_strength": 50,
                "confidence": 0,
                "reasoning": "Analysis failed",
                "error": str(e),
            }

    def _build_analysis_prompt(
        self,
        token_data: Dict[str, Any],
        wallet_data: List[Dict[str, Any]],
        historical_performance: Optional[Dict[str, Any]],
    ) -> str:
        """Build analysis prompt for LLM.

        Args:
            token_data: Token info
            wallet_data: Wallet info
            historical_performance: Historical data

        Returns:
            Formatted prompt
        """
        # Format wallet data
        wallets_summary = []
        for w in wallet_data[:5]:  # Top 5
            wallets_summary.append(
                f"- 30D PnL: ${w.get('pnl_30d', 0):,.0f}, "
                f"Best Trade: {w.get('best_multiple', 0):.1f}x, "
                f"EarlyScore: {w.get('earlyscore', 0):.0f}"
            )

        wallets_text = "\n".join(wallets_summary)

        hist_text = ""
        if historical_performance:
            hist_text = f"""
Historical Performance Context:
- Win Rate (last 24h): {historical_performance.get('win_rate', 0):.1f}%
- Average Return: {historical_performance.get('avg_return', 0):.1f}%
- Total Alerts: {historical_performance.get('total_alerts', 0)}
"""

        prompt = f"""You are a crypto trading analyst. Analyze this token buy signal and provide a structured assessment.

Token Information:
- Symbol: {token_data.get('symbol', 'Unknown')}
- Price: ${token_data.get('price_usd', 0):.6f}
- Market Cap: ${token_data.get('market_cap_usd', 0):,.0f}
- Liquidity: ${token_data.get('liquidity_usd', 0):,.0f}
- 24h Volume: ${token_data.get('volume_24h_usd', 0):,.0f}
- 24h Change: {token_data.get('price_change_24h', 0):.1f}%
- Holder Count: {token_data.get('holder_count', 0)}
- Created: {token_data.get('created_at', 'Unknown')}

Wallets That Bought:
{wallets_text}

{hist_text}

Analyze this signal and respond in JSON format with:
{{
  "signal_strength": 0-100,
  "confidence": 0-100,
  "recommendation": "BUY" | "HOLD" | "AVOID",
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "EXTREME",
  "reasoning": "Brief explanation",
  "positive_signals": ["signal1", "signal2"],
  "red_flags": ["flag1", "flag2"]
}}

Focus on:
1. Wallet quality (PnL, win rate)
2. Token fundamentals (liquidity, holder distribution)
3. Market conditions
4. Risk factors (low liquidity, concentration, rapid price moves)

Response (JSON only):"""

        return prompt

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM API.

        Args:
            prompt: Analysis prompt

        Returns:
            LLM response text
        """
        try:
            # Ollama API format
            response = await self.client.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # More deterministic
                        "top_p": 0.9,
                    },
                },
            )

            response.raise_for_status()
            result = response.json()

            return result.get("response", "")

        except Exception as e:
            logger.error(f"LLM query error: {str(e)}")
            raise

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response.

        Args:
            response: LLM text response

        Returns:
            Parsed analysis dict
        """
        try:
            # Try to extract JSON from response
            # LLM might include extra text, so find JSON block
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                logger.warning("No JSON found in LLM response")
                return {}

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            return {}

    async def generate_alert_summary(
        self,
        alerts: List[Dict[str, Any]],
        timeframe: str = "24h",
    ) -> str:
        """Generate natural language summary of alerts.

        Args:
            alerts: List of alert data
            timeframe: Time period

        Returns:
            Summary text
        """
        prompt = f"""Summarize these crypto trading alerts from the last {timeframe}:

{json.dumps(alerts, indent=2)}

Provide a concise summary highlighting:
1. Most interesting opportunities
2. Common patterns
3. Risk warnings
4. Overall market sentiment

Keep it under 200 words and actionable."""

        try:
            response = await self._query_llm(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Summary generation error: {str(e)}")
            return "Summary generation failed."

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()


# Example usage with different LLM backends

class OpenAIAnalyzer(LLMSignalAnalyzer):
    """Use OpenAI API (or compatible)."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        super().__init__(
            api_url="https://api.openai.com/v1/chat/completions",
            model=model,
        )

    async def _query_llm(self, prompt: str) -> str:
        """Query OpenAI API."""
        response = await self.client.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )

        response.raise_for_status()
        result = response.json()

        return result["choices"][0]["message"]["content"]


class LocalLMStudioAnalyzer(LLMSignalAnalyzer):
    """Use LM Studio (local models)."""

    def __init__(self, port: int = 1234, model: str = "local-model"):
        super().__init__(
            api_url=f"http://localhost:{port}/v1/chat/completions",
            model=model,
        )

    async def _query_llm(self, prompt: str) -> str:
        """Query LM Studio API (OpenAI-compatible)."""
        response = await self.client.post(
            self.api_url,
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            },
        )

        response.raise_for_status()
        result = response.json()

        return result["choices"][0]["message"]["content"]
