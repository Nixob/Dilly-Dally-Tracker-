import streamlit as st
import pandas as pd
from supabase import create_client

# ---------- Setup ----------
st.set_page_config(page_title="MLBB Match Log", page_icon="🎮", layout="centered")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ROLES = ["Roam", "Exp", "Jungle", "Mid", "Gold"]
QUEUES = ["Solo", "Duo", "Trio", "5-Stack"]

RATING_COLS = {
    "focus": "Focus Level",
    "teammate_quality": "Teammate Quality",
    "opponent_quality": "Opponent Quality",
    "team_draft": "Team Draft Quality",
    "enemy_draft": "Enemy Draft Difficulty",
}


def load_matches():
    res = supabase.table("matches").select("*").order("created_at", desc=True).execute()
    return pd.DataFrame(res.data)


def add_match(entry):
    supabase.table("matches").insert(entry).execute()


def delete_match(match_id):
    supabase.table("matches").delete().eq("id", match_id).execute()


# ---------- Header ----------
st.title("MLBB Match Log")
st.caption("Track every match. Find the pattern.")

df = load_matches()

if not df.empty:
    total = len(df)
    wins = (df["result"] == "win").sum()
    winrate = round(wins / total * 100)
else:
    total, wins, winrate = 0, 0, 0

c1, c2, c3 = st.columns(3)
c1.metric("Matches", total)
c2.metric("Winrate", f"{winrate}%")
c3.metric("Wins", wins)

st.divider()

# ---------- Log a match ----------
st.subheader("Log a Match")

with st.form("log_match", clear_on_submit=True):
    hero = st.text_input("Hero")
    col1, col2 = st.columns(2)
    with col1:
        role = st.selectbox("Role", ROLES)
    with col2:
        queue = st.selectbox("Queue Type", QUEUES)

    result = st.radio("Result", ["win", "loss"], horizontal=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        kills = st.number_input("Kills", min_value=0, step=1, value=0)
    with col_b:
        deaths = st.number_input("Deaths", min_value=0, step=1, value=0)
    with col_c:
        assists = st.number_input("Assists", min_value=0, step=1, value=0)

    medal = st.selectbox("Medal", ["None", "Bronze", "Silver", "Gold", "MVP"])

    focus = st.slider("Focus Level", 1, 5, 3)
    teammate_quality = st.slider("Teammate Quality", 1, 5, 3)
    opponent_quality = st.slider("Opponent Quality", 1, 5, 3)
    team_draft = st.slider("Team Draft Quality", 1, 5, 3)
    enemy_draft = st.slider("Enemy Draft Difficulty", 1, 5, 3)

    notes = st.text_area("Notes", placeholder="what went well, what to fix next time...")

    submitted = st.form_submit_button("Save Match", use_container_width=True)

    if submitted:
        if not hero.strip():
            st.error("Enter a hero name before saving.")
        else:
            add_match({
                "hero": hero.strip(),
                "role": role,
                "queue": queue,
                "result": result,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "medal": medal,
                "focus": focus,
                "teammate_quality": teammate_quality,
                "opponent_quality": opponent_quality,
                "team_draft": team_draft,
                "enemy_draft": enemy_draft,
                "notes": notes.strip(),
            })
            st.success(f"Saved: {hero} ({result})")
            st.rerun()

st.divider()

# ---------- Breakdown ----------
st.subheader("Breakdown")

if df.empty:
    st.caption("No matches logged yet.")
else:
    tab_hero, tab_role, tab_queue = st.tabs(["By Hero", "By Role", "By Queue"])

    def breakdown_table(group_col):
        grouped = df.groupby(group_col).agg(
            matches=("result", "count"),
            wins=("result", lambda x: (x == "win").sum())
        )
        grouped["winrate"] = (grouped["wins"] / grouped["matches"] * 100).round(0).astype(int).astype(str) + "%"
        grouped = grouped.sort_values("matches", ascending=False)[["matches", "winrate"]]
        st.dataframe(grouped, use_container_width=True)

    with tab_hero:
        breakdown_table("hero")
    with tab_role:
        breakdown_table("role")
    with tab_queue:
        breakdown_table("queue")

st.divider()

# ---------- Performance Insights ----------
st.subheader("Performance Insights")
st.caption("Does this factor actually affect your winrate?")

if df.empty:
    st.caption("Log a few matches first to see patterns.")
else:
    insight_tabs = st.tabs(list(RATING_COLS.values()))

    for tab, (col, label) in zip(insight_tabs, RATING_COLS.items()):
        with tab:
            grouped = df.groupby(col).agg(
                matches=("result", "count"),
                wins=("result", lambda x: (x == "win").sum())
            )
            grouped["winrate"] = (grouped["wins"] / grouped["matches"] * 100).round(0)

            # only show ratings with at least 1 match, fill gaps 1-5 for a clean axis
            grouped = grouped.reindex(range(1, 6)).dropna(subset=["matches"])

            if grouped.empty or len(grouped) < 2:
                st.caption("Not enough spread in your data yet — log matches at different rating levels to see a trend.")
            else:
                st.bar_chart(grouped["winrate"])
                st.caption(f"Winrate (%) by {label}, 1 = lowest, 5 = highest")

                # quick average comparison: this rating in wins vs losses
                avg_win = df[df["result"] == "win"][col].mean()
                avg_loss = df[df["result"] == "loss"][col].mean()
                colA, colB = st.columns(2)
                colA.metric(f"Avg {label} in wins", round(avg_win, 1))
                colB.metric(f"Avg {label} in losses", round(avg_loss, 1))

st.divider()

# ---------- Biggest Factor ----------
st.subheader("What Matters Most")
st.caption("Ranked by how much each factor differs between your wins and losses")

if df.empty or len(df) < 4:
    st.caption("Log a few more matches to unlock this.")
else:
    factor_gaps = []
    for col, label in RATING_COLS.items():
        avg_win = df[df["result"] == "win"][col].mean()
        avg_loss = df[df["result"] == "loss"][col].mean()
        gap = round(avg_win - avg_loss, 2)
        factor_gaps.append({"Factor": label, "Avg in Wins": round(avg_win, 1), "Avg in Losses": round(avg_loss, 1), "Gap": gap})

    gap_df = pd.DataFrame(factor_gaps)
    gap_df["Abs Gap"] = gap_df["Gap"].abs()
    gap_df = gap_df.sort_values("Abs Gap", ascending=False).drop(columns="Abs Gap")

    st.dataframe(gap_df, use_container_width=True, hide_index=True)

    top = gap_df.iloc[0]
    direction = "higher" if top["Gap"] > 0 else "lower"
    st.info(f"**{top['Factor']}** shows the biggest split — your wins average a {direction} rating here than your losses (gap of {abs(top['Gap'])}).")

st.divider()

# ---------- Match history ----------
st.subheader("Match History")

if df.empty:
    st.caption("No matches logged yet. Add your first one above.")
else:
    for _, row in df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{row['hero']}** · {row['role']} · {row['queue']} queue")
                st.caption(
                    f"{row['kills']}/{row['deaths']}/{row['assists']} KDA · {row['medal']} medal · "
                    f"Focus {row['focus']} · Teammates {row['teammate_quality']} · "
                    f"Opponents {row['opponent_quality']} · Team Draft {row['team_draft']} · "
                    f"Enemy Draft {row['enemy_draft']}"
                )
                if row["notes"]:
                    st.caption(f"_{row['notes']}_")
            with col2:
                badge = "🟢 WIN" if row["result"] == "win" else "🔴 LOSS"
                st.markdown(f"**{badge}**")
                if st.button("Delete", key=f"del_{row['id']}"):
                    delete_match(row["id"])
                    st.rerun()
