import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from PIL import Image
import time

# USER = 'xxx'
# PASSW = 'xxxxx'
USER = st.secrets["USER"]
PASSW = st.secrets["PASSW"]

if 'user_state' not in st.session_state:
    st.session_state.user_state = {
        'username': '',
        'password': '',
        'logged_in': False
    }

def login():
    """Gestisce il login dell'utente."""
    st.title('Login Richieste Fascicoli')
    logo = Image.open('FBS.jpg')
    if logo:
        st.image(logo, width=600)
    username = st.text_input('Username')
    password = st.text_input('Password', type='password')
    submit = st.button('Login', type="primary")
    if submit:
        if username == USER and password == PASSW:
            st.session_state.user_state['username'] = username
            st.session_state.user_state['password'] = password
            st.session_state.user_state['logged_in'] = True
            st.success('You are logged in')
            st.rerun()
        else:
            st.error('Invalid username or password')

####################################################################################################
credentials = {
                "type": st.secrets["type"],
                "project_id": st.secrets["project_id"],
                "private_key_id": st.secrets["private_key_id"],
                "private_key": st.secrets["private_key"],
                "client_email": st.secrets["client_email"],
                "client_id": st.secrets["client_id"],
                "auth_uri": st.secrets["auth_uri"],
                "token_uri": st.secrets["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["client_x509_cert_url"]
                }

@st.cache_data(ttl=30)  # Cache per 30 secondi
def load_data():
    """Carica i dati da Google Sheets."""
    gc = gspread.service_account_from_dict(credentials)
    gsheetId = st.secrets["gsheet_id"] 
    sh = gc.open_by_key(gsheetId)
    
    # Get worksheets
    database_w = sh.worksheet("database")
    prenotazioni_w = sh.worksheet("prenotazioni")
    gestori_w = sh.worksheet("gestori")
    centri_costo_w = sh.worksheet("centri_costo")

    # Load data
    database = pd.DataFrame(database_w.get_all_records())
    prenotazioni = pd.DataFrame(prenotazioni_w.get_all_records())
    gestori = pd.DataFrame(gestori_w.get_all_records())    
    centri_costo = pd.DataFrame(centri_costo_w.get_all_records())    

    # Converti le stringhe booleane in booleani
    bool_columns = ['PRENOTATO', 'RESTITUITO', 'DISPONIBILE']
    for col in bool_columns:
        if col in prenotazioni.columns:
            prenotazioni[col] = prenotazioni[col].map({'TRUE': True, 'FALSE': False})
    
    # Load gestori data
    return database, prenotazioni, gestori, centri_costo

def save_prenotazione(prenotazioni, new_prenotazione):
    """Salva una nuova prenotazione in Google Sheets aggiungendo una nuova riga."""
    gc = gspread.service_account_from_dict(credentials)
    gsheetId = st.secrets["gsheet_id"] 
    sh = gc.open_by_key(gsheetId)
    prenotazioni_w = sh.worksheet("prenotazioni")
    
    # Converti i valori booleani in stringhe
    for key in ['PRENOTATO', 'RESTITUITO', 'DISPONIBILE']:
        if key in new_prenotazione:
            new_prenotazione[key] = str(new_prenotazione[key]).upper()

    required_columns = [
                        'PORTAFOGLIO', 'NDG', 'MOTIVAZIONE_RICHIESTA', 'DATA_RICHIESTA',
                        'PRENOTATO', 'RESTITUITO', 'DATA_EVASIONE', 'DATA_RESTITUZIONE',
                        'NOME_RICHIEDENTE', 'COGNOME_RICHIEDENTE', 'GESTORE', 'NOTE', 'DISPONIBILE',
                        'CENTRO_COSTO','PORTAFOGLIO_CC','INTESTAZIONE'
                        ]
    
    # Prepara la nuova riga da aggiungere
    new_row = [str(new_prenotazione.get(col, '')) for col in required_columns]
    
    # Aggiungi la nuova riga al foglio
    prenotazioni_w.append_row(new_row)
    
    # Aggiorna il DataFrame delle prenotazioni aggiungendo la nuova riga
    new_df = pd.DataFrame([new_prenotazione])
    prenotazioni_updated = pd.concat([prenotazioni, new_df], ignore_index=True)
    
    # Pulisci la cache per forzare il ricaricamento dei dati
    load_data.clear()
    
    return prenotazioni_updated

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

    # Pulsante per ricaricare i dati
    if st.sidebar.button("🔄 Ricarica Dati"):
        load_data.clear()
        st.rerun()

    # Inizializza lo stato della sessione
    if 'search_clicked' not in st.session_state:
        st.session_state.search_clicked = False
    if 'nome' not in st.session_state:
        st.session_state.nome = ""
    if 'cognome' not in st.session_state:
        st.session_state.cognome = ""

    try:
        database, prenotazioni, gestori,centri_costo = load_data()
        # Crea una maschera per le prenotazioni attive
        active_prenotations = prenotazioni[prenotazioni['RESTITUITO'] != True]
        # Crea un DataFrame base dalla fusione di database e prenotazioni
        df = database.copy()
        # Se ci sono prenotazioni attive, filtra per combinazione NDG/Portafoglio/Motivazione
        if len(active_prenotations) > 0:
            # Crea una chiave univoca per il controllo delle prenotazioni
            active_prenotations['check_key'] = active_prenotations.apply(
                lambda x: f"{x['NDG']}_{x['PORTAFOGLIO']}_{x['MOTIVAZIONE_RICHIESTA']}", 
                axis=1
            )
            df['DISPONIBILE'] = True
        else:
            df['DISPONIBILE'] = True

    except Exception as e:
        st.error(f"Errore nel caricamento dei dati: {str(e)}")
        st.stop()
    
    st.sidebar.header("Filtri di Ricerca")

    ## PORTAFOGLI    
    portafogli_list = sorted(df['PORTAFOGLIO'].unique())
    portafoglio_selezionato = st.sidebar.selectbox(
                                                    "Seleziona Portafoglio",
                                                    options=[''] + portafogli_list,
                                                    index=0
                                                    )
    if portafoglio_selezionato == '':
        st.sidebar.markdown('<p class="required">La selezione del Portafoglio è obbligatoria</p>', 
                          unsafe_allow_html=True)

    ## CENTRI COSTO 
    centri_costo_list = sorted(centri_costo['CENTRO_COSTO'].unique())
    centri_costo_selezionato = st.sidebar.selectbox(
                                                    "Seleziona Centro di Costo",
                                                    options=[''] + centri_costo_list,
                                                    index=0
                                                    )
    if centri_costo_selezionato == '':
        st.sidebar.markdown('<p class="required">La selezione del centro di costo è obbligatoria</p>', 
                          unsafe_allow_html=True)

    ## NDG
    ndg_list = get_ndg_list(df, portafoglio_selezionato if portafoglio_selezionato != '' else None)
    ndg_selezionato = st.sidebar.selectbox(
                                        "Seleziona NDG *",
                                        options=[''] + ndg_list,
                                        index=0
                                        )
    if ndg_selezionato == '':
        st.sidebar.markdown('<p class="required">La selezione del NDG è obbligatoria</p>', 
                          unsafe_allow_html=True)

    ## MOTIVAZIONI
    motivazioni_list = [
                    "azionare-posizione-consegna STA",
                    "analisi documenti - scansione fascicolo",
                    "scansione documenti specifici",
                    "richiesta originali specifici"
                    ]
    motivazione_selezionata = st.sidebar.selectbox(
                                                    "Motivazione Richiesta",
                                                    options=[''] + motivazioni_list,
                                                    index=0
                                                    )

    if motivazione_selezionata == '':
        st.sidebar.markdown('<p class="required">La selezione della Motivazione è obbligatoria</p>', 
                          unsafe_allow_html=True)

    def handle_search():
        if ndg_selezionato == '':
            st.sidebar.error("Devi selezionare un NDG prima di cercare")
        else:
            st.session_state.search_clicked = True

    if st.sidebar.button("Cerca", on_click=handle_search):
        pass

    # Logica di ricerca e visualizzazione risultati
    if st.session_state.search_clicked and ndg_selezionato != '':
        # Applica i filtri
        mask = pd.Series(True, index=df.index)
        if portafoglio_selezionato:
            mask &= df['PORTAFOGLIO'] == portafoglio_selezionato
        if ndg_selezionato:
            mask &= df['NDG'].astype(str) == ndg_selezionato
        
        risultati = df[mask]
        
        if len(risultati) > 0:
            # Verifica se esiste già una prenotazione con la stessa combinazione
            if motivazione_selezionata:
                check_key = f"{ndg_selezionato}_{portafoglio_selezionato}_{motivazione_selezionata}"
                if len(active_prenotations) > 0 and check_key in active_prenotations['check_key'].values:
                    st.warning(f"Esiste già una prenotazione attiva per questo NDG/Portafoglio con la motivazione: {motivazione_selezionata}")
                else:
                    # Mostra i risultati
                    for _, row in risultati.iterrows():
                        st.markdown(f"""
                            <div style='color: #87CEEB'>
                                <h5> Portafoglio: {row['PORTAFOGLIO']} - NDG: {row['NDG']} - Intestazione: {row['INTESTAZIONE']} </h5>
                                <h5> Numero Scatola: {row['NUMERO_SCATOLA']} - ID_CREDITLINE: {row['ID_CREDITLINE']} - Tipologia Documento: {row['TIPOLOGIA_DOCUMENTO']}</h5>
                            </div>
                            """, unsafe_allow_html=True)
                            
                    # Form per la prenotazione
                    st.markdown("### Informazioni Richiedente")
                    st.markdown("I campi contrassegnati con * sono obbligatori")
                    
                    # Input Nome e Cognome
                    col1, col2 = st.columns(2)
                    with col1:
                        nome = st.text_input("Nome *", 
                                           value=st.session_state.nome,
                                           key="nome_input").strip()
                        st.session_state.nome = nome
                        if not nome:
                            st.markdown('<p class="required">Il nome è obbligatorio</p>', 
                                      unsafe_allow_html=True)

                    with col2:
                        cognome = st.text_input("Cognome *", 
                                              value=st.session_state.cognome,
                                              key="cognome_input").strip()
                        st.session_state.cognome = cognome
                        if not cognome:
                            st.markdown('<p class="required">Il cognome è obbligatorio</p>', 
                                      unsafe_allow_html=True)

                    with col1:
                        gestore_list = sorted(gestori['NOME_VIS'].unique())
                        gestore_selezionato = st.selectbox(
                            "Seleziona Gestore *",
                            options=[''] + gestore_list,
                            index=0
                        )
                        if gestore_selezionato == '':
                            st.markdown('<p class="required">Il Gestore è obbligatorio</p>', 
                                      unsafe_allow_html=True)

                    note = ""
                    if motivazione_selezionata in ["scansione documenti specifici", 
                                                 "richiesta originali specifici"]:
                        st.markdown("INSERIRE TUTTE LE RICHIESTE ALL'INTERNO DELLE NOTE, ALTRIMENTI NON SARA' POSSIBILE FARLO PRIMA CHE LA RICHIESTA VENGA EVASA TOTALMENTE")
                        note = st.text_area("Note aggiuntive", key="note")

                    if st.button("Prenota Fascicolo"):
                        if ndg_selezionato and motivazione_selezionata:
                            if not nome or not cognome or not gestore_selezionato:
                                st.error("Nome, Cognome e Gestore sono campi obbligatori")
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
                                                        'DATA_EVASIONE': '',
                                                        'DATA_RESTITUZIONE': '',
                                                        'NOME_RICHIEDENTE': nome,
                                                        'COGNOME_RICHIEDENTE': cognome,
                                                        'GESTORE': gestore_selezionato,
                                                        'DISPONIBILE': False,
                                                        'CENTRO_COSTO' : centri_costo_selezionato,
                                                        'PORTAFOGLIO_CC' : '',
                                                        'INTESTAZIONE' : '',
                                                        }
                                    prenotazioni = save_prenotazione(prenotazioni, new_prenotazione)
                                    
                                    # Feedback all'utente
                                    st.success("Fascicolo prenotato con successo!")
                                    st.session_state.search_clicked = False
                                    st.session_state.nome = ""
                                    st.session_state.cognome = ""
                                    st.session_state.gestore = ""
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

    # Informazioni di riepilogo nella sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Informazioni Database")
    st.sidebar.info(f"""
        - Portafogli disponibili: {len(portafoglio_selezionato)}
        - Totale fascicoli: {len(df)}
    """)

def main():
    """Funzione principale dell'applicazione."""
    if not st.session_state.user_state['logged_in']:
        login()
    else:
        main_app()

if __name__ == "__main__":
    main()