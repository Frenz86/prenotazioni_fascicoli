import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread


@st.cache_data(ttl=300)  # Cache per 5 minuti (300 secondi)
def load_data():
    """Carica i dati da Google Sheets con cache."""
    gc = gspread.service_account(filename='google_sa.json')
    gsheetId = '150mxH0wbZmXp3cJMWRC1P5r5jjLYfX3rR0z7pFnB5TY'
    sh = gc.open_by_key(gsheetId)
    database_w = sh.worksheet("database")
    prenotazioni_w = sh.worksheet("prenotazioni")
    database_json = database_w.get_all_records()
    prenotazioni_json = prenotazioni_w.get_all_records()

    database = pd.DataFrame(database_json)
    prenotazioni = pd.DataFrame(prenotazioni_json)
    prenotazioni['PRENOTATO'] = prenotazioni['PRENOTATO'].astype(bool)
    prenotazioni['RESTITUITO'] = prenotazioni['RESTITUITO'].astype(bool)
    prenotazioni['DISPONIBILE'] = prenotazioni['DISPONIBILE'].astype(bool)
    if not prenotazioni.empty:
        prenotazioni.loc[prenotazioni['RESTITUITO'] == True, 'PRENOTATO'] = False
        prenotazioni['DISPONIBILE'] = ~prenotazioni['PRENOTATO']
    return database, prenotazioni

def save_prenotazione(prenotazioni_df, new_prenotazione):
    """Salva una nuova prenotazione in Google Sheets."""
    gc = gspread.service_account(filename='google_sa.json')
    gsheetId = '150mxH0wbZmXp3cJMWRC1P5r5jjLYfX3rR0z7pFnB5TY'
    sh = gc.open_by_key(gsheetId)
    prenotazioni_sheet = sh.worksheet("prenotazioni")
    
    # Prepara i dati da inserire
    values = []
    for key in prenotazioni_sheet.row_values(1):
        values.append(str(new_prenotazione.get(key, '')))
    
    # Aggiungi la nuova riga
    prenotazioni_sheet.append_row(values)
    # Invalida la cache dopo il salvataggio
    load_data.clear()
    prenotazioni_df = pd.concat([prenotazioni_df, pd.DataFrame([new_prenotazione])], ignore_index=True)
    prenotazioni_df = prenotazioni_df.drop_duplicates(subset=['NDG', 'PORTAFOGLIO'], keep='last')
    
    return prenotazioni_df

def get_ndg_list(df, portafoglio_selezionato=None):
    """Restituisce la lista di NDG filtrata per portafoglio."""
    if portafoglio_selezionato:
        filtered_df = df[df['PORTAFOGLIO'] == portafoglio_selezionato]
    else:
        filtered_df = df
    return sorted(filtered_df['NDG'].unique().astype(str))

def main_app():
    st.markdown("""
        <style>
        .required {
            color: red;
            margin-left: 5px;
        }
        .required-field label::after {
            content: ' *';
            color: red;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("Richieste Fascicoli FBS")    
    
    if 'search_clicked' not in st.session_state:
        st.session_state.search_clicked = False
    if 'nome' not in st.session_state:
        st.session_state.nome = ""
    if 'cognome' not in st.session_state:
        st.session_state.cognome = ""

    # Aggiungi pulsante per ricaricare i dati
    if st.sidebar.button("🔄 Ricarica Dati"):
        load_data.clear()
        st.rerun()

    database, prenotazioni = load_data()
    
    if database.empty or prenotazioni.empty:
        st.error("Impossibile caricare i dati. Riprova più tardi.")
        return

    df = database.merge(prenotazioni, how='left')
    df = df[df['DISPONIBILE'] != False]
    
    st.sidebar.header("Filtri di Ricerca")    
    
    portafogli = sorted(df['PORTAFOGLIO'].unique())
    portafoglio_selezionato = st.sidebar.selectbox(
        "Seleziona Portafoglio",
        options=[''] + portafogli,
        index=0
    )
    
    ndg_list = get_ndg_list(df, portafoglio_selezionato if portafoglio_selezionato != '' else None)
    ndg_selected = st.sidebar.selectbox(
        "Seleziona NDG",
        options=[''] + ndg_list,
        index=0
    )

    def handle_search():
        if ndg_selected:
            st.session_state.search_clicked = True

    st.sidebar.button(
        "Cerca",
        on_click=handle_search,
        disabled=not ndg_selected
    )
    
    if not ndg_selected:
        st.sidebar.warning("Seleziona un NDG per effettuare la ricerca")

    if st.session_state.search_clicked:
        mask = pd.Series(True, index=df.index)
        if portafoglio_selezionato:
            mask &= df['PORTAFOGLIO'] == portafoglio_selezionato
        if ndg_selected:
            mask &= df['NDG'].astype(str) == ndg_selected
        
        risultati = df[mask]
        
        if len(risultati) > 0:            
            for _, row in risultati.iterrows():
                st.write(f"NDG: {row['NDG']} - Portafoglio: {row['PORTAFOGLIO']} - Intestazione: {row['INTESTAZIONE']} - Numero Scatola: {row['NUMERO_SCATOLA']}")            
            
            st.markdown("### Informazioni Richiedente")
            st.markdown("I campi contrassegnati con * sono obbligatori")
            
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input(
                    "Nome *",
                    value=st.session_state.nome,
                    key="nome_input"
                ).strip()
                st.session_state.nome = nome
                if not nome:
                    st.markdown('<p class="required">Il nome è obbligatorio</p>', unsafe_allow_html=True)

            with col2:
                cognome = st.text_input(
                    "Cognome *",
                    value=st.session_state.cognome,
                    key="cognome_input"
                ).strip()
                st.session_state.cognome = cognome
                if not cognome:
                    st.markdown('<p class="required">Il cognome è obbligatorio</p>', unsafe_allow_html=True)
            
            motivazioni = [
                "azionare-posizione-consegna STA",
                "analisi documenti - scansione fascicolo",
                "scansione documenti specifici",
                "richiesta originali specifici"
            ]
            motivazione_selezionata = st.selectbox(
                "Motivazione Richiesta",
                options=[''] + motivazioni,
                index=0
            )
            
            note = ""
            if motivazione_selezionata in ["scansione documenti specifici", "richiesta originali specifici"]:
                note = st.text_area("Note aggiuntive", key="note")
            
            if st.button("Prenota Fascicolo"):
                if ndg_selected and motivazione_selezionata:
                    if not nome or not cognome:
                        st.error("Nome e cognome sono campi obbligatori")
                    else:
                        row = risultati.iloc[0]
                        new_prenotazione = {
                            'NDG': row['NDG'],
                            'PORTAFOGLIO': row['PORTAFOGLIO'],
                            'DATA_RICHIESTA': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'MOTIVAZIONE_RICHIESTA': motivazione_selezionata,
                            'NOTE': note,
                            'PRENOTATO': True,
                            'RESTITUITO': False,
                            'NOME_RICHIEDENTE': nome,
                            'COGNOME_RICHIEDENTE': cognome,
                            'DISPONIBILE': False,
                        }
                        prenotazioni = save_prenotazione(prenotazioni, new_prenotazione)
                        
                        st.success("Fascicolo prenotato con successo!")
                        st.session_state.search_clicked = False
                        st.session_state.nome = ""
                        st.session_state.cognome = ""
                        st.balloons()
                        #time.sleep(1)
                        st.rerun()
                else:
                    if not motivazione_selezionata:
                        st.error("Seleziona una motivazione prima di prenotare")
                    else:
                        st.error("Seleziona un Portafoglio & NDG da prenotare")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Informazioni Database")
    st.sidebar.info(f"""
        - Portafogli disponibili: {len(portafogli)}
        - Fascicoli Totali: {len(df)}
    """)

if __name__ == "__main__":
    main_app()