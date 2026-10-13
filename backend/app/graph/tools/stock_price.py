import yfinance as yf
from langchain_core.tools import tool


def _format_large_number(val: float) -> str:
    """Format large numbers into human-readable strings (T, B, M)."""
    if val is None:
        return "N/A"
    try:
        abs_val = abs(val)
        if abs_val >= 1e12:
            return f"${val / 1e12:.2f}T"
        if abs_val >= 1e9:
            return f"${val / 1e9:.2f}B"
        if abs_val >= 1e6:
            return f"${val / 1e6:.2f}M"
        return f"${val:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _get_single_stock_info(symbol: str) -> str:
    """Fetch and format stock information for a single ticker."""
    sym = symbol.strip().upper()
    if not sym:
        return "Invalid symbol provided."

    try:
        ticker = yf.Ticker(sym)
        info = ticker.info

        # Check if valid ticker data was returned
        curr_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if curr_price is None:
            # Fallback to fast_info
            try:
                curr_price = ticker.fast_info.last_price
            except Exception:
                curr_price = None

        if curr_price is None:
            return f"Could not find stock data for ticker '{sym}'. Please check the symbol."

        name = info.get("shortName") or info.get("longName") or sym
        currency = info.get("currency", "USD")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        open_price = info.get("open") or info.get("regularMarketOpen")
        day_low = info.get("dayLow") or info.get("regularMarketDayLow")
        day_high = info.get("dayHigh") or info.get("regularMarketDayHigh")
        w52_low = info.get("fiftyTwoWeekLow")
        w52_high = info.get("fiftyTwoWeekHigh")
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE") or info.get("forwardPE")
        volume = info.get("volume") or info.get("regularMarketVolume")

        # Price movement
        change_str = ""
        if prev_close:
            change = curr_price - prev_close
            pct_change = (change / prev_close) * 100
            sign = "+" if change >= 0 else ""
            change_str = f" ({sign}{change:.2f}, {sign}{pct_change:.2f}%)"

        lines = [
            f"### {name} ({sym})",
            f"- **Current Price**: {currency} {curr_price:.2f}{change_str}",
        ]

        if open_price is not None:
            lines.append(f"- **Open**: {open_price:.2f} | **Previous Close**: {prev_close:.2f}" if prev_close else f"- **Open**: {open_price:.2f}")
        if day_low is not None and day_high is not None:
            lines.append(f"- **Day Range**: {day_low:.2f} - {day_high:.2f}")
        if w52_low is not None and w52_high is not None:
            lines.append(f"- **52-Week Range**: {w52_low:.2f} - {w52_high:.2f}")
        if market_cap:
            lines.append(f"- **Market Cap**: {_format_large_number(market_cap)}")
        if pe_ratio:
            lines.append(f"- **P/E Ratio**: {pe_ratio:.2f}")
        if volume:
            lines.append(f"- **Volume**: {volume:,}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error retrieving data for ticker '{sym}': {str(e)}"


@tool
def get_stock_price(ticker: str) -> str:
    """
    Get current stock price, price change, market metrics, and range for stocks, ETFs, or crypto using Yahoo Finance (yfinance).

    Parameters:
    - ticker (str): The ticker symbol to look up (e.g., 'AAPL', 'MSFT', 'TSLA', 'NVDA', 'BTC-USD', 'SPY', 'RELIANCE.NS').
      Can also take multiple comma-separated tickers (e.g., 'AAPL, TSLA, NVDA').
    """
    clean_input = ticker.strip()
    if not clean_input:
        return "Please provide a valid stock ticker symbol (e.g., 'AAPL', 'MSFT', 'TSLA')."

    # Support multiple comma-separated tickers
    symbols = [s.strip() for s in clean_input.split(",") if s.strip()]
    if not symbols:
        return "Please provide at least one ticker symbol."

    results = []
    for s in symbols[:5]:  # limit to 5 tickers per request
        results.append(_get_single_stock_info(s))

    return "\n\n".join(results)
