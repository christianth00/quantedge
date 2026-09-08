import { fmtNum } from "../fmt.js";

export async function pollMenthorQ() {
  try {
    const res = await fetch("/api/menthorq");
    if (!res.ok) return;
    const data = await res.json();
    
    const body = document.querySelector("#panel-quant .panel-body");
    const foot = document.querySelector("#panel-quant .panel-foot");
    
    if (Object.keys(data).length === 0) {
      body.innerHTML = "<div class='muted' style='padding: 10px;'>Waiting for background fetch...</div>";
      return;
    }

    const tickers = Object.keys(data);
    if (tickers.length === 0) return;
    
    const firstTicker = tickers[0];
    const indicators = Object.keys(data[firstTicker]);

    const header = "<tr><th>Level</th>" + tickers.map(t => "<th>" + t + "</th>").join("") + "</tr>";
    
    const rows = indicators.map(ind => {
      const cells = tickers.map(t => "<td>" + fmtNum(data[t][ind]) + "</td>").join("");
      return "<tr><td class='sym'>" + ind + "</td>" + cells + "</tr>";
    }).join("");

    body.innerHTML = "<table>" + header + rows + "</table>";
    foot.textContent = "DATA: MENTHORQ (LIVE GAMMA LEVELS)";
  } catch (err) {
    console.error("Failed to poll MenthorQ", err);
  }
}

setInterval(pollMenthorQ, 60_000);
pollMenthorQ();
