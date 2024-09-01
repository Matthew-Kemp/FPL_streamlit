import streamlit as st
import pandas as pd
import requests

# Set up Streamlit app title
st.title("FPL Mini-League Dashboard")

# Define your FPL mini-league ID
league_id = '1116305'

# Fetch player data globally (to avoid refetching every time)
@st.cache_data
def fetch_player_data():
    player_data_url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    player_response = requests.get(player_data_url)
    player_response.raise_for_status()
    player_data = player_response.json()
    element_to_player = {player['id']: {'name': player['web_name'], 'price': player['now_cost']} for player in player_data['elements']}
    return element_to_player

element_to_player = fetch_player_data()

# Function to fetch team data
def get_team_data(league_id):
    standings_url = f'https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/'
    response = requests.get(standings_url)
    response.raise_for_status()
    standings_data = response.json()['standings']['results']
    
    teams_data = []
    player_ownership = {}

    for i, team in enumerate(standings_data):
        entry_id = team['entry']
        
        history_url = f'https://fantasy.premierleague.com/api/entry/{entry_id}/history/'
        history_response = requests.get(history_url)
        history_response.raise_for_status()
        history_data = history_response.json()

        picks_url = f'https://fantasy.premierleague.com/api/entry/{entry_id}/event/{history_data["current"][-1]["event"]}/picks/'
        picks_response = requests.get(picks_url)
        picks_response.raise_for_status()
        picks_data = picks_response.json()
        
        for pick in picks_data['picks']:
            player_id = pick['element']
            if player_id in player_ownership:
                player_ownership[player_id] += 1
            else:
                player_ownership[player_id] = 1

        transfers_url = f'https://fantasy.premierleague.com/api/entry/{entry_id}/transfers/'
        transfers_response = requests.get(transfers_url)
        transfers_response.raise_for_status()
        transfers_data = transfers_response.json()

        transfers_by_gw = {}
        for transfer in transfers_data:
            gw_event = transfer['event']
            if gw_event not in transfers_by_gw:
                transfers_by_gw[gw_event] = []
            transfers_by_gw[gw_event].append({
                'in': {
                    'name': element_to_player[transfer['element_in']]['name'],
                    'price': transfer['element_in_cost'] / 10
                },
                'out': {
                    'name': element_to_player[transfer['element_out']]['name'],
                    'price': transfer['element_out_cost'] / 10
                }
            })

        for gw in history_data['current']:
            gw_event = gw['event']
            gw_data = {
                'team_name': team['entry_name'],
                'manager_name': team['player_name'],
                'total_points': team['total'],
                'gameweek': gw_event,
                'points': gw['points'],
                'num_transfers': len(transfers_by_gw.get(gw_event, [])),
                'transfers': transfers_by_gw.get(gw_event, []),
                'chip_played': gw.get('chip', 'None')
            }
            teams_data.append(gw_data)

    return teams_data, player_ownership

teams_data, player_ownership = get_team_data(league_id)

# Convert the teams_data into a DataFrame
df = pd.DataFrame(teams_data)

# Create the points table
df_points = df.pivot_table(index=['team_name', 'manager_name', 'total_points'], columns='gameweek', values='points').reset_index()

# Rename columns for readability
df_points.columns = ['Team Name', 'Manager Name', 'Total Points'] + [f"GW {col}" for col in df_points.columns[3:]]

# Create the transfers table
df_transfers = df.pivot_table(index=['team_name', 'manager_name'], columns='gameweek', values='num_transfers').reset_index()

# Calculate total transfers for each team
df_transfers['total_transfers'] = df_transfers.iloc[:, 2:].sum(axis=1)

# Rename columns for readability
df_transfers.columns = ['Team Name', 'Manager Name'] + [f"GW {col}" for col in df_transfers.columns[2:-1]] + ['Total Transfers']

# Order by total points for the points table and by total transfers for the transfers table
df_points_sorted = df_points.sort_values(by='Total Points', ascending=False).reset_index(drop=True)
df_transfers_sorted = df_transfers.sort_values(by='Total Transfers', ascending=False).reset_index(drop=True)

# Convert all points and transfer columns to integers
points_columns = df_points_sorted.columns[3:]
df_points_sorted[points_columns] = df_points_sorted[points_columns].astype(int)
df_transfers_sorted[df_transfers_sorted.columns[2:-1]] = df_transfers_sorted[df_transfers_sorted.columns[2:-1]].fillna(0).astype(int)

# Prepare the ownership DataFrame
total_teams = len(df['team_name'].unique())
ownership_data = [
    {
        'player_name': element_to_player[player_id]['name'],
        'ownership_fraction': f"{count} / {total_teams}",
        'ownership_percentage': (count / total_teams) * 100
    }
    for player_id, count in player_ownership.items()
]

df_ownership = pd.DataFrame(ownership_data)
df_ownership_sorted = df_ownership.sort_values(by='ownership_percentage', ascending=False).reset_index(drop=True)

# Rename columns for readability
df_ownership_sorted.columns = ['Player Name', 'Ownership (Fraction)', 'Ownership (%)']

# Add the tabs
tab1, tab2, tab3 = st.tabs(["Gameweek Points", "Transfers Summary", "Most-Owned Players"])

with tab1:
    # Display the sorted points table without the index
    st.write("### Gameweek Points Table")
    st.dataframe(df_points_sorted, height=600, use_container_width=True)

with tab2:
    # Display the sorted transfers table without the index
    st.write("### Transfers Summary Table")
    st.dataframe(df_transfers_sorted, height=600, use_container_width=True)

with tab3:
    # Display the sorted ownership table without the index
    st.write("### Most-Owned Players Table")
    st.dataframe(df_ownership_sorted[['Player Name', 'Ownership (Fraction)']], height=600, use_container_width=True)
