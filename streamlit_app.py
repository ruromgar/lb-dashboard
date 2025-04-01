import streamlit as st
from src.death_race_manager import DeathRaceManager


if __name__ == "__main__":
    drm = DeathRaceManager("unnonueve", "garciamorales")
    drm.main()
    # st.title("Letterboxd Race")

    # user1 = st.text_input("Enter the first username")
    # user2 = st.text_input("Enter the second username")

    # if user1 and user2:
    #     st.write(f"You selected {user1} and {user2}!")
    
    #     if st.button("Show Race"):
    #         drm = DeathRaceManager("unnonueve", "garciamorales")#(user1, user2)  #("unnonueve", "garciamorales")
    #         drm.main()
