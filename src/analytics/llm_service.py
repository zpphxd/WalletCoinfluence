"""On-demand LLM analysis service with smart activation."""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)


class OnDemandLLMService:
    """LLM service that only activates when high-confidence analysis is needed."""

    def __init__(
        self,
        ollama_url: str = "http://ollama:11434",
        model: str = "phi3:latest",
        activation_threshold: float = 75.0,  # Only activate for strong signals
    ):
        """Initialize on-demand LLM service.

        Args:
            ollama_url: Ollama API URL
            model: Model to use
            activation_threshold: Min signal score to trigger LLM
        """
        self.ollama_url = ollama_url
        self.model = model
        self.activation_threshold = activation_threshold
        self.client = None
        self._last_used = None
        self._cache = {}  # Simple in-memory cache

    def should_analyze(self, preliminary_score: float, token_data: Dict[str, Any]) -> bool:
        """Determine if LLM analysis is needed.

        Args:
            preliminary_score: Initial rule-based score (0-100)
            token_data: Token metadata

        Returns:
            True if LLM should analyze
        """
        # Only use LLM for high-potential signals
        if preliminary_score < self.activation_threshold:
            return False

        # Skip if very new (< 5 min old) - too early for LLM
        if token_data.get("age_minutes", 999) < 5:
            return False

        # Skip if liquidity too low (< $10k) - likely scam
        if token_data.get("liquidity_usd", 0) < 10000:
            return False

        # Activate for confluence signals (multiple wallets)
        if token_data.get("num_wallets", 1) >= 2:
            return True

        # Activate for labeled wallets
        if token_data.get("has_labeled_wallet", False):
            return True

        # Activate if preliminary score is very high
        if preliminary_score >= 85:
            return True

        return False

    async def analyze_if_needed(
        self,
        token_data: Dict[str, Any],
        wallet_data: list,
        preliminary_score: float,
    ) -> Optional[Dict[str, Any]]:
        """Analyze signal only if criteria met.

        Args:
            token_data: Token information
            wallet_data: Wallet information
            preliminary_score: Initial score

        Returns:
            LLM analysis or None if skipped
        """
        if not self.should_analyze(preliminary_score, token_data):
            logger.debug(
                f"Skipping LLM for {token_data.get('symbol')} "
                f"(score={preliminary_score:.1f})"
            )
            return None

        logger.info(
            f"Activating LLM for {token_data.get('symbol')} "
            f"(score={preliminary_score:.1f})"
        )

        # Check cache first
        cache_key = f"{token_data.get('token_address')}_{len(wallet_data)}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.utcnow() - cached['timestamp']).seconds < 300:  # 5 min
                logger.debug("Using cached LLM analysis")
                return cached['result']

        # Ensure client is connected
        await self._ensure_client()

        # Run analysis with optimized prompt
        analysis = await self._analyze_with_optimized_prompt(
            token_data, wallet_data, preliminary_score
        )

        # Cache result
        self._cache[cache_key] = {
            'result': analysis,
            'timestamp': datetime.utcnow()
        }

        # Clean old cache entries
        self._clean_cache()

        self._last_used = datetime.utcnow()

        return analysis

    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)

    async def _analyze_with_optimized_prompt(
        self,
        token_data: Dict[str, Any],
        wallet_data: list,
        preliminary_score: float,
    ) -> Dict[str, Any]:
        """Run LLM analysis with highly optimized prompt.

        Args:
            token_data: Token info
            wallet_data: Wallet info
            preliminary_score: Initial score

        Returns:
            Analysis result
        """
        # Build ultra-concise, structured prompt
        prompt = self._build_optimized_prompt(token_data, wallet_data, preliminary_score)

        try:
            response = await self.client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Very deterministic
                        "top_p": 0.9,
                        "num_predict": 200,  # Short response
                    },
                },
            )

            response.raise_for_status()
            result = response.json()

            llm_response = result.get("response", "")

            # Parse response
            return self._parse_optimized_response(llm_response, preliminary_score)

        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}")
            return {
                "signal_strength": preliminary_score,  # Fall back to preliminary
                "confidence": 0,
                "recommendation": "HOLD",
                "error": str(e),
            }

    def _build_optimized_prompt(
        self,
        token_data: Dict[str, Any],
        wallet_data: list,
        preliminary_score: float,
    ) -> str:
        """Build ultra-optimized, token-efficient prompt.

        Args:
            token_data: Token info
            wallet_data: Wallet info
            preliminary_score: Initial score

        Returns:
            Optimized prompt
        """
        # Condense wallet data
        wallets_summary = []
        for w in wallet_data[:3]:  # Max 3 wallets
            pnl = w.get('pnl_30d', 0)
            mult = w.get('best_multiple', 0)
            early = w.get('earlyscore', 0)
            name = w.get('name', '')
            wallets_summary.append(
                f"{'✓' + name if name else 'Wallet'}: ${pnl/1000:.0f}k PnL, {mult:.1f}x best, {early:.0f} early"
            )

        wallets_text = " | ".join(wallets_summary)

        # Ultra-concise prompt (token-efficient)
        prompt = f"""Crypto signal analysis. Respond ONLY with: CONFIDENCE(0-100) | ACTION(BUY/HOLD/AVOID) | REASON(1 sentence)

Token: {token_data.get('symbol')}
Price: ${token_data.get('price_usd', 0):.8f}
MCap: ${token_data.get('market_cap_usd', 0)/1000:.0f}k
Liq: ${token_data.get('liquidity_usd', 0)/1000:.0f}k
Vol24h: ${token_data.get('volume_24h_usd', 0)/1000:.0f}k
Holders: {token_data.get('holder_count', 0)}
Age: {token_data.get('age_minutes', 0):.0f}min

Wallets: {wallets_text}

Preliminary Score: {preliminary_score:.0f}/100

Rules:
- BUY only if confidence >80 AND no red flags
- AVOID if low liq (<$30k), high concentration, or memecoin spam
- Consider wallet quality + token fundamentals

Response:"""

        return prompt

    def _parse_optimized_response(
        self, response: str, fallback_score: float
    ) -> Dict[str, Any]:
        """Parse LLM's optimized response.

        Args:
            response: LLM response
            fallback_score: Score to use if parsing fails

        Returns:
            Parsed analysis
        """
        try:
            # Expected format: "85 | BUY | Strong wallets, good liquidity"
            parts = response.strip().split("|")

            if len(parts) >= 3:
                confidence = int(parts[0].strip())
                action = parts[1].strip().upper()
                reason = parts[2].strip()

                return {
                    "signal_strength": confidence,
                    "confidence": confidence,
                    "recommendation": action,
                    "reasoning": reason,
                    "risk_level": self._infer_risk(confidence, action),
                }

            # Fallback parsing
            logger.warning(f"Unexpected LLM format: {response}")
            return self._fallback_parse(response, fallback_score)

        except Exception as e:
            logger.error(f"Parse error: {str(e)}")
            return {
                "signal_strength": fallback_score,
                "confidence": 50,
                "recommendation": "HOLD",
                "reasoning": "Parse failed",
            }

    def _fallback_parse(self, response: str, fallback_score: float) -> Dict[str, Any]:
        """Fallback parsing if structured format fails.

        Args:
            response: LLM response
            fallback_score: Fallback score

        Returns:
            Best-effort parsed result
        """
        response_lower = response.lower()

        # Infer recommendation from keywords
        if "buy" in response_lower and "avoid" not in response_lower:
            recommendation = "BUY"
            confidence = 75
        elif "avoid" in response_lower or "risky" in response_lower:
            recommendation = "AVOID"
            confidence = 70
        else:
            recommendation = "HOLD"
            confidence = 60

        return {
            "signal_strength": confidence,
            "confidence": confidence,
            "recommendation": recommendation,
            "reasoning": response[:200],  # First 200 chars
            "risk_level": "MEDIUM",
        }

    def _infer_risk(self, confidence: int, action: str) -> str:
        """Infer risk level from confidence and action.

        Args:
            confidence: Confidence score
            action: Recommended action

        Returns:
            Risk level
        """
        if action == "AVOID":
            return "EXTREME"
        elif action == "BUY" and confidence > 85:
            return "LOW"
        elif action == "BUY":
            return "MEDIUM"
        else:
            return "MEDIUM"

    def _clean_cache(self) -> None:
        """Remove cache entries older than 10 minutes."""
        now = datetime.utcnow()
        to_remove = []

        for key, value in self._cache.items():
            if (now - value['timestamp']).seconds > 600:  # 10 min
                to_remove.append(key)

        for key in to_remove:
            del self._cache[key]

    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None


# Global instance
llm_service = OnDemandLLMService()
