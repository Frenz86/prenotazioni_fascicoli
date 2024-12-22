import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.credentials import Credentials

def load_data():
    """Carica i dati da Google Sheets."""
    gc = gspread.service_account(filename='google_sa.json')
    gsheetId = '150mxH0wbZmXp3cJMWRC1P5r5jjLYfX3rR0z7pFnB5TY'
    sh = gc.open_by_key(gsheetId)
    
    # Get worksheets
    database_w = sh.worksheet("database")
    prenotazioni_w = sh.worksheet("prenotazioni")
    
    # Load data
    database = pd.DataFrame(database_w.get_all_records())
    prenotazioni = pd.DataFrame(prenotazioni_w.get_all_records())
    
    # Converti le stringhe booleane in booleani
    bool_columns = ['PRENOTATO', 'RESTITUITO', 'DISPONIBILE']
    for col in bool_columns:
        if col in prenotazioni.columns:
            prenotazioni[col] = prenotazioni[col].map({'TRUE': True, 'FALSE': False})
    
    # Set PRENOTATO to False when RESTITUITO is True
    prenotazioni.loc[prenotazioni['RESTITUITO'] == True, 'PRENOTATO'] = False
    
    return database, prenotazioni

def save_prenotazione(prenotazioni, new_prenotazione):
    """Salva una nuova prenotazione in Google Sheets."""
    gc = gspread.service_account(filename='google_sa.json')
    gsheetId = '150mxH0wbZmXp3cJMWRC1P5r5jjLYfX3rR0z7pFnB5TY'
    sh = gc.open_by_key(gsheetId)
    prenotazioni_w = sh.worksheet("prenotazioni")
    
    # Converti i valori booleani in stringa nel nuovo record
    for key in ['PRENOTATO', 'RESTITUITO', 'DISPONIBILE']:
        if key in new_prenotazione:
            new_prenotazione[key] = str(new_prenotazione[key]).upper()

    # Crea una copia delle colonne necessarie per le prenotazioni
    required_columns = [
                        'NDG', 'PORTAFOGLIO', 'MOTIVAZIONE_RICHIESTA',
                        'NOTE', 'PRENOTATO', 'RESTITUITO','DATA_RICHIESTA','DATA_EVASIONE', 'NOME_RICHIEDENTE', 'COGNOME_RICHIEDENTE','DISPONIBILE'
                    ]
    
    # Filtra il DataFrame prenotazioni per includere solo le colonne necessarie
    prenotazioni_filtered = prenotazioni[required_columns].copy() if len(prenotazioni) > 0 else pd.DataFrame(columns=required_columns)
    
    # Crea un nuovo DataFrame con solo le colonne necessarie dal nuovo record
    new_record = {k: v for k, v in new_prenotazione.items() if k in required_columns}
    new_df = pd.DataFrame([new_record])
    
    # Aggiungi la nuova prenotazione al DataFrame filtrato
    prenotazioni_updated = pd.concat([prenotazioni_filtered, new_df], ignore_index=True)
    prenotazioni_updated = prenotazioni_updated.drop_duplicates(subset=['NDG', 'PORTAFOGLIO'], keep='last')
    
    # Converti i valori booleani in stringa nel DataFrame completo
    bool_columns = ['PRENOTATO', 'RESTITUITO']
    for col in bool_columns:
        if col in prenotazioni_updated.columns:
            prenotazioni_updated[col] = prenotazioni_updated[col].astype(str).str.upper()
    
    # Assicurati che tutti i valori siano compatibili con JSON
    for col in prenotazioni_updated.columns:
        prenotazioni_updated[col] = prenotazioni_updated[col].fillna('').astype(str)
    
    # Converti il DataFrame in lista di liste per Google Sheets
    headers = required_columns
    values = prenotazioni_updated.values.tolist()
    
    # Aggiorna il foglio prenotazioni
    prenotazioni_w.clear()
    prenotazioni_w.update([headers] + values)
    
    return prenotazioni_updated
    

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

    try:
        database, prenotazioni = load_data()
        df = database.merge(prenotazioni, on=['NDG', 'PORTAFOGLIO'], how='left', indicator=True)
        # Gestione colonna PRENOTATO
        df['PRENOTATO'] = df['PRENOTATO'].fillna(False)
        # Calcolo DISPONIBILE
        df['DISPONIBILE'] = ~df['PRENOTATO']        
        df = df[df['DISPONIBILE'] == True]
        
        # Rimuovi le colonne duplicate e di debug
        columns_to_drop = [col for col in df.columns if col.endswith('_y')] + ['_merge']
        df = df.drop(columns=columns_to_drop)
    except Exception as e:
        st.error(f"Errore nel caricamento dei dati: {str(e)}")
        st.stop()
    
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
                        try:
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
                                'DATA_EVASIONE':None,
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
                        except Exception as e:
                            st.error(f"Errore nel salvare la prenotazione: {str(e)}")
                else:
                    if not motivazione_selezionata:
                        st.error("Seleziona una motivazione prima di prenotare")
                    else:
                        st.error("Seleziona un NDG da prenotare")
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