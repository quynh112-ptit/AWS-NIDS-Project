"""Shared presentation for the SOC dashboard and mobile demo."""
import streamlit as st

STYLE = """
<style>
:root {
    --nids-ink: #eef5ff;
    --nids-muted: #a0b2ce;
    --nids-mint: #53e6c0;
    --nids-edge: #253653;
    --nids-surface: #101d31;
}
[data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at 88% 0%, #142a43 0%, #0b1220 47%);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { padding-top: 3.1rem; padding-bottom: 2.5rem; }
[data-testid="stSidebar"] { border-right: 1px solid var(--nids-edge); }
[data-testid="stSidebar"] [data-testid="stImage"] img {
    border: 8px solid white; border-radius: 16px; background: white;
}
.nids-brand {
    display: flex; align-items: center; gap: .55rem; margin: 0 0 .65rem;
    color: var(--nids-mint); font-size: .74rem; font-weight: 800;
    letter-spacing: .19em; text-transform: uppercase;
}
.nids-mark {
    display: inline-grid; place-items: center; width: 28px; height: 28px;
    color: #081e1c; background: var(--nids-mint); border-radius: 8px;
    font-size: .82rem; letter-spacing: 0;
}
.nids-hero {
    padding: 1.35rem 1.55rem; border-radius: 20px; border: 1px solid #2d4666;
    background: linear-gradient(118deg, #132139 10%, #123045 72%, #12383c 100%);
    box-shadow: 0 14px 36px #030b1740;
}
.nids-hero h1 {
    color: var(--nids-ink); font-size: clamp(1.65rem, 3.7vw, 2.65rem);
    font-weight: 780; letter-spacing: -.045em; line-height: 1.14; margin: 0;
    padding: 0;
}
.nids-heading {
    color: var(--nids-ink); font-weight: 700; font-size: 1.04rem;
    margin: 0 0 .55rem; letter-spacing: -.012em;
}
.nids-small {
    color: var(--nids-muted); font-size: .74rem; font-weight: 650;
    text-transform: uppercase; letter-spacing: .12em; margin: 0 0 .55rem;
}
.nids-status {
    display: inline-flex; align-items: center; gap: .42rem; color: #abbbd1;
    font-size: .77rem; font-weight: 600;
}
.nids-status::before {
    content: ""; width: 7px; height: 7px; border-radius: 50%;
    background: var(--nids-mint); box-shadow: 0 0 12px #53e6c088;
}
.nids-kpi {
    min-height: 112px; padding: .95rem 1.06rem; border: 1px solid var(--nids-edge);
    border-radius: 15px; background: var(--nids-surface);
    border-top: 2px solid var(--nids-accent, var(--nids-mint));
}
.nids-kpi-label { font-size: .79rem; color: var(--nids-muted); font-weight: 650; }
.nids-kpi-value {
    margin-top: .28rem; color: var(--nids-ink); font-size: clamp(1.65rem, 4vw, 2.15rem);
    font-weight: 780; line-height: 1.16; letter-spacing: -.045em; font-variant-numeric: tabular-nums;
}
[class*="st-key-soc-panel"] {
    padding: .95rem 1.05rem .65rem; border: 1px solid var(--nids-edge);
    border-radius: 15px; background: var(--nids-surface);
}
[data-testid="stForm"] {
    background: var(--nids-surface); border: 1px solid var(--nids-edge);
    border-radius: 18px; padding: 1.15rem;
}
[data-testid="stRadio"] div[role="radiogroup"] {
    display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: .55rem;
}
[data-testid="stRadio"] div[role="radiogroup"] > label {
    margin: 0; padding: .72rem .58rem; background: #14253c;
    border: 1px solid var(--nids-edge); border-radius: 10px; min-width: 0;
}
[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
    background: #133735; border-color: var(--nids-mint);
}
[data-testid="stFormSubmitButton"] button {
    font-weight: 750; min-height: 2.8rem; border-radius: 10px;
}
@media (max-width: 640px) {
    [data-testid="stMainBlockContainer"] { padding-top: 2.65rem; padding-left: 1rem; padding-right: 1rem; }
    .nids-hero { padding: 1.08rem; }
    [data-testid="stForm"] { padding: .86rem; }
    [data-testid="stRadio"] div[role="radiogroup"] > label { padding: .55rem .38rem; }
}
</style>
"""


def apply_theme():
    st.html(STYLE)


def hero(title, section):
    st.html(f"""
    <header class="nids-hero">
        <div class="nids-brand"><span class="nids-mark" aria-hidden="true">◆</span> NIDS / {section}</div>
        <h1>{title}</h1>
    </header>
    """)


def heading(title):
    st.html(f'<h2 class="nids-heading">{title}</h2>')


def kpi(label, value, accent):
    st.html(f"""
    <div class="nids-kpi" style="--nids-accent:{accent}">
        <div class="nids-kpi-label">{label}</div>
        <div class="nids-kpi-value">{value}</div>
    </div>
    """)
