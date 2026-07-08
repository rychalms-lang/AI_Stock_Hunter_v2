from datetime import datetime


def pct(value):
    try:
        value = float(value)
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.2f}%"
    except Exception:
        return "N/A"


def money(value):
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "N/A"


def badge_color(value):
    if value >= 80:
        return "#16a34a"
    if value >= 60:
        return "#ca8a04"
    return "#dc2626"


def create_text_report(market, sectors, ranked_stocks, portfolio):
    today = datetime.now().strftime("%B %d, %Y")

    lines = []
    lines.append("AI STOCK HUNTER")
    lines.append("Morning Market Brief")
    lines.append(today)
    lines.append("=" * 50)
    lines.append("")

    lines.append("MARKET REGIME")
    lines.append(f"Regime: {market['regime']}")
    lines.append(f"Market Score: {market['market_score']}/100")
    lines.append(f"Summary: {market['description']}")
    lines.append("")

    lines.append("LEADING SECTORS")
    for i, sector in enumerate(sectors[:5], start=1):
        lines.append(
            f"{i}. {sector['sector']} ({sector['etf']}) | "
            f"5D: {pct(sector['five_day_return'])} | "
            f"20D: {pct(sector['twenty_day_return'])}"
        )
    lines.append("")

    lines.append("TOP PICKS")
    for i, stock in enumerate(ranked_stocks[:10], start=1):
        lines.append("-" * 50)
        lines.append(f"{i}. {stock['ticker']} ({stock.get('sector', 'Unknown')})")
        lines.append(f"Score: {stock.get('score', stock.get('pre_score', 0))}")
        lines.append(f"Confidence: {stock.get('confidence_score', 0)}%")
        lines.append(f"Open: {money(stock.get('latest_open'))}")
        lines.append(f"Close: {money(stock.get('latest_close'))}")
        lines.append(f"Open-to-Close: {pct(stock.get('open_to_close_change'))}")
        lines.append(f"5-Day Change: {pct(stock.get('five_day_change'))}")
        lines.append(f"20-Day Change: {pct(stock.get('twenty_day_change'))}")
        lines.append(f"Relative Strength: {pct(stock.get('relative_strength'))}")
        lines.append("")

        lines.append("Historical Pattern:")
        lines.append(f"Matches: {stock.get('historical_matches', 0)}")
        lines.append(f"Best Hold: {stock.get('best_hold_period', 'Unknown')}")
        lines.append(f"Best Avg Return: {pct(stock.get('best_avg_return', 0))}")
        lines.append(f"1D: {pct(stock.get('pattern_1d_avg_return', 0))} | Win: {pct(stock.get('pattern_1d_win_rate', 0))}")
        lines.append(f"3D: {pct(stock.get('pattern_3d_avg_return', 0))} | Win: {pct(stock.get('pattern_3d_win_rate', 0))}")
        lines.append(f"5D: {pct(stock.get('pattern_5d_avg_return', 0))} | Win: {pct(stock.get('pattern_5d_win_rate', 0))}")
        lines.append(f"7D: {pct(stock.get('pattern_7d_avg_return', 0))} | Win: {pct(stock.get('pattern_7d_win_rate', 0))}")
        lines.append(f"10D: {pct(stock.get('pattern_10d_avg_return', 0))} | Win: {pct(stock.get('pattern_10d_win_rate', 0))}")
        lines.append("")

        lines.append("Why It Ranked:")
        for reason in stock.get("confidence_reasons", []):
            lines.append(f"- {reason}")

        lines.append("")
        lines.append("Risk Flags:")
        for risk in stock.get("risk_flags", []):
            lines.append(f"- {risk}")

        if stock.get("analysis_brief"):
            lines.append("")
            lines.append("Stock Brief:")
            lines.append(stock["analysis_brief"])

        lines.append("")

    lines.append("=" * 50)
    lines.append("PORTFOLIO MODEL")
    lines.append(f"Cash Allocation: {portfolio['cash_allocation']}%")

    for pos in portfolio["positions"]:
        lines.append(
            f"{pos['ticker']}: {pos['allocation_pct']}% "
            f"Confidence: {pos['confidence_score']}%"
        )

    return "\n".join(lines)


def create_html_report(market, sectors, ranked_stocks, portfolio):
    today = datetime.now().strftime("%B %d, %Y")

    stock_cards = ""

    for i, stock in enumerate(ranked_stocks[:10], start=1):
        confidence = stock.get("confidence_score", 0)
        color = badge_color(confidence)

        reasons_html = "".join(
            f"<li>{reason}</li>"
            for reason in stock.get("confidence_reasons", [])
        )

        risks_html = "".join(
            f"<li>{risk}</li>"
            for risk in stock.get("risk_flags", [])
        )

        brief_html = ""
        if stock.get("analysis_brief"):
            brief_html = f"""
            <div class="brief">
                <h4>Stock Brief</h4>
                <p>{stock["analysis_brief"]}</p>
            </div>
            """

        stock_cards += f"""
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="rank">#{i}</div>
                    <h2>{stock['ticker']}</h2>
                    <p class="sector">{stock.get('sector', 'Unknown')}</p>
                </div>
                <div class="confidence" style="background:{color};">
                    {confidence}%
                </div>
            </div>

            <div class="metrics">
                <div><span>Score</span><strong>{stock.get('score', stock.get('pre_score', 0))}</strong></div>
                <div><span>Open</span><strong>{money(stock.get('latest_open'))}</strong></div>
                <div><span>Close</span><strong>{money(stock.get('latest_close'))}</strong></div>
                <div><span>Open → Close</span><strong>{pct(stock.get('open_to_close_change'))}</strong></div>
                <div><span>5D</span><strong>{pct(stock.get('five_day_change'))}</strong></div>
                <div><span>20D</span><strong>{pct(stock.get('twenty_day_change'))}</strong></div>
            </div>

            <div class="historical-box">
                <h4>📚 Historical Pattern</h4>
                <div class="historical-grid">
                    <div>
                        <span>Similar Setups</span>
                        <strong>{stock.get('historical_matches', 0)}</strong>
                    </div>
                    <div>
                        <span>Best Hold</span>
                        <strong>{stock.get('best_hold_period', 'Unknown')}</strong>
                    </div>
                    <div>
                        <span>Best Avg Return</span>
                        <strong>{pct(stock.get('best_avg_return', 0))}</strong>
                    </div>
                </div>

                <table class="pattern-table">
                    <tr>
                        <th>Hold</th>
                        <th>Avg Return</th>
                        <th>Win Rate</th>
                    </tr>
                    <tr>
                        <td>1D</td>
                        <td>{pct(stock.get('pattern_1d_avg_return', 0))}</td>
                        <td>{pct(stock.get('pattern_1d_win_rate', 0))}</td>
                    </tr>
                    <tr>
                        <td>3D</td>
                        <td>{pct(stock.get('pattern_3d_avg_return', 0))}</td>
                        <td>{pct(stock.get('pattern_3d_win_rate', 0))}</td>
                    </tr>
                    <tr>
                        <td>5D</td>
                        <td>{pct(stock.get('pattern_5d_avg_return', 0))}</td>
                        <td>{pct(stock.get('pattern_5d_win_rate', 0))}</td>
                    </tr>
                    <tr>
                        <td>7D</td>
                        <td>{pct(stock.get('pattern_7d_avg_return', 0))}</td>
                        <td>{pct(stock.get('pattern_7d_win_rate', 0))}</td>
                    </tr>
                    <tr>
                        <td>10D</td>
                        <td>{pct(stock.get('pattern_10d_avg_return', 0))}</td>
                        <td>{pct(stock.get('pattern_10d_win_rate', 0))}</td>
                    </tr>
                </table>
            </div>

            <div class="split">
                <div>
                    <h4>Why It Ranked</h4>
                    <ul>{reasons_html}</ul>
                </div>
                <div>
                    <h4>Risk Flags</h4>
                    <ul>{risks_html}</ul>
                </div>
            </div>

            {brief_html}
        </div>
        """

    sector_rows = ""
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    for i, sector in enumerate(sectors[:5]):
        sector_rows += f"""
        <tr>
            <td>{medals[i]}</td>
            <td><strong>{sector['sector']}</strong></td>
            <td>{sector['etf']}</td>
            <td>{pct(sector['five_day_return'])}</td>
            <td>{pct(sector['twenty_day_return'])}</td>
        </tr>
        """

    portfolio_rows = ""

    for pos in portfolio["positions"]:
        portfolio_rows += f"""
        <tr>
            <td><strong>{pos['ticker']}</strong></td>
            <td>{pos.get('sector', 'Unknown')}</td>
            <td>{pos['allocation_pct']}%</td>
            <td>{pos['confidence_score']}%</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background: #0f172a;
                font-family: Arial, Helvetica, sans-serif;
                color: #e5e7eb;
            }}

            .container {{
                max-width: 860px;
                margin: 0 auto;
                padding: 28px;
            }}

            .hero {{
                background: linear-gradient(135deg, #111827, #1e3a8a);
                border-radius: 18px;
                padding: 28px;
                margin-bottom: 24px;
                border: 1px solid #334155;
            }}

            .hero h1 {{
                margin: 0;
                font-size: 34px;
                letter-spacing: -1px;
            }}

            .hero p {{
                margin: 8px 0 0;
                color: #cbd5e1;
            }}

            .section {{
                background: #111827;
                border: 1px solid #334155;
                border-radius: 18px;
                padding: 22px;
                margin-bottom: 24px;
            }}

            .section h2 {{
                margin-top: 0;
                font-size: 22px;
            }}

            .regime {{
                display: inline-block;
                padding: 10px 16px;
                border-radius: 999px;
                font-weight: bold;
                background: #16a34a;
                color: white;
            }}

            .score {{
                font-size: 44px;
                font-weight: bold;
                margin-top: 12px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
            }}

            th, td {{
                text-align: left;
                padding: 12px;
                border-bottom: 1px solid #334155;
            }}

            th {{
                color: #94a3b8;
                font-size: 13px;
                text-transform: uppercase;
            }}

            .card {{
                background: #111827;
                border: 1px solid #334155;
                border-radius: 18px;
                padding: 22px;
                margin-bottom: 22px;
            }}

            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 18px;
            }}

            .rank {{
                color: #94a3b8;
                font-size: 14px;
                margin-bottom: 4px;
            }}

            .card h2 {{
                margin: 0;
                font-size: 28px;
            }}

            .sector {{
                color: #93c5fd;
                margin: 4px 0 0;
            }}

            .confidence {{
                width: 72px;
                height: 72px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 19px;
                color: white;
            }}

            .metrics {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 12px;
                margin-bottom: 20px;
            }}

            .metrics div {{
                background: #0f172a;
                padding: 14px;
                border-radius: 12px;
                border: 1px solid #1e293b;
            }}

            .metrics span,
            .historical-grid span {{
                display: block;
                color: #94a3b8;
                font-size: 12px;
                margin-bottom: 6px;
            }}

            .metrics strong,
            .historical-grid strong {{
                font-size: 18px;
            }}

            .historical-box {{
                background: #0f172a;
                border: 1px solid #2563eb;
                border-radius: 16px;
                padding: 18px;
                margin-bottom: 20px;
            }}

            .historical-box h4 {{
                margin-top: 0;
                color: #bfdbfe;
            }}

            .historical-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 12px;
                margin-bottom: 16px;
            }}

            .historical-grid div {{
                background: #111827;
                border: 1px solid #1e293b;
                border-radius: 12px;
                padding: 12px;
            }}

            .pattern-table td,
            .pattern-table th {{
                padding: 9px;
            }}

            .split {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 18px;
            }}

            h4 {{
                margin-bottom: 8px;
                color: #f8fafc;
            }}

            ul {{
                margin-top: 0;
                padding-left: 20px;
            }}

            li {{
                margin-bottom: 6px;
                color: #cbd5e1;
            }}

            .brief {{
                background: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 14px;
                padding: 16px;
                margin-top: 18px;
            }}

            .brief p {{
                color: #cbd5e1;
                line-height: 1.5;
            }}

            .footer {{
                text-align: center;
                color: #64748b;
                font-size: 12px;
                margin-top: 28px;
            }}

            @media only screen and (max-width: 700px) {{
                .metrics,
                .historical-grid,
                .split {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>

    <body>
        <div class="container">
            <div class="hero">
                <h1>📈 AI Stock Hunter</h1>
                <p>Morning Market Brief • {today}</p>
            </div>

            <div class="section">
                <h2>🌎 Market Regime</h2>
                <div class="regime">{market['regime']}</div>
                <div class="score">{market['market_score']}/100</div>
                <p>{market['description']}</p>

                <table>
                    <tr>
                        <th>Index</th>
                        <th>Trend</th>
                        <th>Score</th>
                        <th>20D Return</th>
                    </tr>
                    <tr>
                        <td>SPY</td>
                        <td>{market['spy']['trend']}</td>
                        <td>{market['spy']['score']}</td>
                        <td>{pct(market['spy']['return_20d'])}</td>
                    </tr>
                    <tr>
                        <td>QQQ</td>
                        <td>{market['qqq']['trend']}</td>
                        <td>{market['qqq']['score']}</td>
                        <td>{pct(market['qqq']['return_20d'])}</td>
                    </tr>
                    <tr>
                        <td>IWM</td>
                        <td>{market['iwm']['trend']}</td>
                        <td>{market['iwm']['score']}</td>
                        <td>{pct(market['iwm']['return_20d'])}</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h2>🏆 Leading Sectors</h2>
                <table>
                    <tr>
                        <th>Rank</th>
                        <th>Sector</th>
                        <th>ETF</th>
                        <th>5D</th>
                        <th>20D</th>
                    </tr>
                    {sector_rows}
                </table>
            </div>

            <div class="section">
                <h2>💼 Portfolio Model</h2>
                <p>Cash Allocation: <strong>{portfolio['cash_allocation']}%</strong></p>
                <table>
                    <tr>
                        <th>Ticker</th>
                        <th>Sector</th>
                        <th>Allocation</th>
                        <th>Confidence</th>
                    </tr>
                    {portfolio_rows}
                </table>
            </div>

            <h2>⭐ Top Picks</h2>
            {stock_cards}

            <div class="footer">
                AI Stock Hunter is a research tool, not financial advice.
            </div>
        </div>
    </body>
    </html>
    """

    return html