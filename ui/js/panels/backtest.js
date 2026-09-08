document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("run-backtest-btn");
    const results = document.getElementById("backtest-results");
    if (btn && results) {
        btn.addEventListener("click", async () => {
            btn.disabled = true;
            btn.innerText = "Running Backtest...";
            results.innerText = "Initializing backtest engine (synthetic data)...";

            const symbols = Array.from(document.querySelectorAll("input[name='symbols']:checked")).map(el => el.value).join(",");
            const strategy = document.getElementById("strategy-select").value;
            const start = document.getElementById("start-date").value;
            const end = document.getElementById("end-date").value;
            const stopTicks = document.getElementById("stop-ticks").value;
            const targetTicks = document.getElementById("target-ticks").value;

            try {
                const res = await fetch(`/api/backtest?symbols=${symbols}&strategy=${strategy}&start=${start}&end=${end}&stop=${stopTicks}&target=${targetTicks}`);
                const data = await res.json();
                results.innerText = data.output || data.status;
            } catch (err) {
                results.innerText = "Error: " + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = "Run Strategy";
            }
        });
    }

    const gmmBtn = document.getElementById("run-gmm-btn");
    if (gmmBtn) {
        gmmBtn.addEventListener("click", async () => {
            gmmBtn.disabled = true;
            gmmBtn.innerText = "Calculating...";
            
            try {
                const res = await fetch(`/api/dynamic-stop?symbol=GC`);
                const data = await res.json();
                if (data.error) throw new Error(data.error);
                
                let text = `[Regime Detection Complete]\nMarket Regime: ${data.regime_name} (Class ${data.current_regime})\n`;
                text += `Current Volatility: ${data.current_volatility_pct.toFixed(2)}%\n`;
                text += `Base Stop Ticks: ${data.base_stop}\n`;
                text += `DYNAMIC STOP LOSS: ${data.dynamic_stop} TICKS`;
                
                document.getElementById("gmm-results").innerText = text;
            } catch(err) {
                document.getElementById("gmm-results").innerText = "Error: " + err.message;
            } finally {
                gmmBtn.disabled = false;
                gmmBtn.innerText = "Calculate GMM Dynamic Stop (GC)";
            }
        });
    }
});
