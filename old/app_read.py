
import streamlit as st
import pandas as pd
import os

path = "dati/db_fascicoli.xlsx"

def load_data():
    df = pd.read_excel(path,sheet_name="database")
    prenotazioni = pd.read_excel(path,sheet_name="prenotazioni")
    return df,prenotazioni

def main():
    st.title("Richieste Fascicoli Prenotabili")    
    database, prenotazioni = load_data() 

    df = database.merge(prenotazioni,how='left')
    ## filtro non prenotati
    df = df[df['PRENOTATO'] != True]
    st.sidebar.header("Filtri di Ricerca")    
    # Menu a tendina per il portafoglio
    portafogli = sorted(df['PORTAFOGLIO'].unique())
    portafoglio_selezionato = st.sidebar.selectbox(
                                                    "Seleziona Portafoglio",
                                                    options=[''] + portafogli,  # Aggiungi opzione vuota
                                                    index=0,  # Seleziona l'opzione vuota come default
                                                    )
    ndg_query = st.sidebar.text_input("Inserisci NDG")
    if st.sidebar.button("Cerca"):
        mask = pd.Series(True, index=df.index)
        if portafoglio_selezionato:
            mask &= df['PORTAFOGLIO'] == portafoglio_selezionato
        if ndg_query:
            mask &= df['NDG'].astype(str).str.contains(ndg_query, case=False)
        risultati = df[mask]

        # Mostra i risultati
        if len(risultati) > 0:
            st.success(f"Trovati {len(risultati)} risultati")
            st.dataframe(risultati)
        else:
            st.warning("Nessun risultato trovato per i criteri di ricerca specificati")

        st.subheader("Statistiche della ricerca")
        st.write(f"- Totale record nel database: {len(df)}")
        st.write(f"- Record trovati: {len(risultati)}")
        if portafoglio_selezionato:
            total_portafoglio = len(df[df['PORTAFOGLIO'] == portafoglio_selezionato])
            st.write(f"- Totale record per il portafoglio {portafoglio_selezionato}: {total_portafoglio}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Informazioni Database")
    st.sidebar.info(f"""
                    - Totale record: {len(df)}
                    - Portafogli disponibili: {len(portafogli)}
                    """)

# MOTIVAZIONE_RICHIESTA
# azionare-posizione-consegna STA
# analisi documenti - scansione fascicolo
# scansione documenti specifici -  inserire nota
# richiesta originali specifici - inserire nota

# se uno già richiesto non devee richiedere
# inoltre se non disponibile

if __name__ == "__main__":
    main()