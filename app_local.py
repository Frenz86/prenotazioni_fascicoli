import streamlit as st
import pandas as pd
from datetime import datetime


########################################################
######### google shet
########################################################
# gc = gspread.service_account(filename='google_sa.json')
# gsheetId = '150mxH0wbZmXp3cJMWRC1P5r5jjLYfX3rR0z7pFnB5TY'
# sh = gc.open_by_key(gsheetId)
# # Get worksheets
# database_w = sh.worksheet("database")
# prenotazioni_w = sh.worksheet("prenotazioni")
# # Load data
# database_json = database_w.get_all_records()
# prenotazioni_json = prenotazioni_w.get_all_records()
# # Convert to DataFrames
# database = pd.DataFrame(database_json)
# prenotazioni = pd.DataFrame(prenotazioni_json)

path = "dati/db_fascicoli.xlsx"

def load_data():
    """Carica i dati dal file Excel."""
    df = pd.read_excel(path, sheet_name="database")
    prenotazioni = pd.read_excel(path, sheet_name="prenotazioni")
    # Set PRENOTATO to False when RESTITUITO is True
    prenotazioni.loc[prenotazioni['RESTITUITO'] == True, 'PRENOTATO'] = False
    return df, prenotazioni

def save_prenotazione(prenotazioni_df, new_prenotazione):
    """Salva una nuova prenotazione nel file Excel."""
    excel_file = pd.ExcelFile(path)
    sheets = {}
    for sheet_name in excel_file.sheet_names:
        if sheet_name != 'prenotazioni':  # Saltiamo il foglio prenotazioni che aggiorneremo
            sheets[sheet_name] = pd.read_excel(path, sheet_name=sheet_name)
    
    # Aggiungi la nuova prenotazione al DataFrame delle prenotazioni
    prenotazioni_df = pd.concat([prenotazioni_df, pd.DataFrame([new_prenotazione])], ignore_index=True)
    prenotazioni_df = prenotazioni_df.drop_duplicates(subset=['NDG', 'PORTAFOGLIO'], keep='last')
    sheets['prenotazioni'] = prenotazioni_df
    # Salva tutti i fogli nel nuovo file Excel
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    return prenotazioni_df

def get_ndg_list(df, portafoglio_selezionato=None):
    """Restituisce la lista di NDG filtrata per portafoglio."""
    if portafoglio_selezionato:
        filtered_df = df[df['PORTAFOGLIO'] == portafoglio_selezionato]
    else:
        filtered_df = df
    return sorted(filtered_df['NDG'].unique().astype(str))

def main():
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

    database, prenotazioni = load_data() 
    df = database.merge(prenotazioni, how='left')
    df['DISPONIBILE'] = 1-df['PRENOTATO'] #negato
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
        st.session_state.search_clicked = True

    if st.sidebar.button("Cerca", on_click=handle_search):
        pass
    # Logica di ricerca e visualizzazione risultati
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
            # Informazioni richiedente
            st.markdown("### Informazioni Richiedente")
            st.markdown("I campi contrassegnati con * sono obbligatori")
            
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome *", 
                                   value=st.session_state.nome,
                                   key="nome_input").strip()
                st.session_state.nome = nome
                if not nome:
                    st.markdown('<p class="required">Il nome è obbligatorio</p>', unsafe_allow_html=True)

            with col2:
                cognome = st.text_input("Cognome *", 
                                      value=st.session_state.cognome,
                                      key="cognome_input").strip()
                st.session_state.cognome = cognome
                if not cognome:
                    st.markdown('<p class="required">Il cognome è obbligatorio</p>', unsafe_allow_html=True)
            
            # Menu a tendina per la motivazione
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
            
            # Campo note - mostrato solo per specifiche motivazioni
            note = ""
            if motivazione_selezionata in ["scansione documenti specifici", "richiesta originali specifici"]:
                note = st.text_area("Note aggiuntive", key="note")
            
            # Bottone per confermare la prenotazione
            if st.button("Prenota Fascicolo"):
                if ndg_selected and motivazione_selezionata:
                    if not nome or not cognome:
                        st.error("Nome e cognome sono campi obbligatori")
                    else:
                        # Crea la nuova prenotazione
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
                        # Salva la prenotazione
                        prenotazioni = save_prenotazione(prenotazioni, new_prenotazione)
                        
                        st.success("Fascicolo prenotato con successo!")
                        st.session_state.search_clicked = False
                        st.session_state.nome = ""
                        st.session_state.cognome = ""
                        st.success('Richiesta inoltrata')
                        st.balloons()
                        st.rerun()
                else:
                    if not motivazione_selezionata:
                        st.error("Seleziona una motivazione prima di prenotare")
                    else:
                        st.error("Seleziona un NDG da prenotare")

            # st.subheader("Statistiche della ricerca")
            # st.write(f"- Totale record nel database: {len(df)}")
            # st.write(f"- Record trovati: {len(risultati)}")
            # if portafoglio_selezionato:
            #     total_portafoglio = len(df[df['PORTAFOGLIO'] == portafoglio_selezionato])
            #     st.write(f"- Totale record per il portafoglio {portafoglio_selezionato}: {total_portafoglio}")
        else:
            st.warning("Nessun risultato trovato per i criteri di ricerca specificati")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Informazioni Database")
    st.sidebar.info(f"""
                    - Totale fascicoli: {len(df)}
                    - Portafogli disponibili: {len(portafogli)}
                    """)

if __name__ == "__main__":
    main()