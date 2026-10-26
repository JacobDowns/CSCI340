"""Lab 3 starter: familiar game and save rows as Polars DataFrames."""

import polars as pl

games = pl.DataFrame(
    {
        "game_id": [1, 2, 3],
        "title": ["Starfall Cartographers", "Mosslight", "Circuit Garden"],
    }
)

saves = pl.DataFrame(
    {
        "save_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "player_id": [1, 1, 2, 1, 3, 3, 2, 2],
        "game_id": [1, 1, 1, 1, 2, 2, 3, 3],
        "completion_percent": [25.0, 50.0, 49.99, 75.0, 80.0, 100.0, None, 80.0],
    }
)

# Worked example: saves whose recorded completion is at least 80%.
high_saves = (
    saves.filter(pl.col("completion_percent") >= 80)
    .select("save_id", "game_id", "completion_percent")
    .sort("save_id")
)
print("Worked example: saves at 80% or more")
print(high_saves)

# A. Group by game_id. Count all saves and non-null completion values.
#    Save the result as by_game and sort by game_id.

# B. Add a conditional count of saves at 80% or more. Save the full
#    grouped result as game_summary, then filter it to games with >= 3 saves.

# C. Join the full game_summary to games on game_id. Show each game's title
#    and counts, sorted by title.
