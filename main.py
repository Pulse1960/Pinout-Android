from datetime import datetime
import os
import shutil
import sqlite3
import zipfile

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserIconView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scatter import Scatter
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.utils import platform

# Gestion du dossier de stockage sur Android vs PC
def get_storage_dir():
  if platform == "android":
    from android.storage import app_storage_path
    return app_storage_path()
  return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_storage_dir()
DB_PATH = os.path.join(BASE_DIR, "base_emmc.db")
IMG_DIR = os.path.join(BASE_DIR, "pinouts")
os.makedirs(IMG_DIR, exist_ok=True)


class ZoomableImage(Scatter):
  """Permet le zoom à deux doigts (pinch-to-zoom) et le déplacement sur écran tactile."""

  def __init__(self, source="", **kwargs):
    super().__init__(
        do_rotation=False,
        do_scale=True,
        do_translation=True,
        scale_min=0.5,
        scale_max=8.0,
        **kwargs,
    )
    self.img = KivyImage(source=source, allow_stretch=True, keep_ratio=True)
    self.add_widget(self.img)

  def set_source(self, source):
    self.scale = 1.0
    self.pos = (0, 0)
    self.img.source = source
    self.img.reload()


class PinoutMobileApp(App):

  def build(self):
    self.title = "eMMC & Pinout - By Ahmed KEMMAR V1.2"
    self.selected_photos = []
    self.init_db()

    root = BoxLayout(orientation="vertical", padding=8, spacing=8)

    # --- BARRE SUPÉRIEURE ---
    top_bar = BoxLayout(size_hint_y=None, height=45, spacing=5)
    top_bar.add_widget(
        Label(
            text="[b]By Ahmed KEMMAR V1.2[/b]",
            markup=True,
            size_hint_x=0.45,
            font_size="13sp",
        )
    )
    btn_exp = Button(
        text="Export ZIP", size_hint_x=0.27, background_color=(0.1, 0.5, 0.8, 1)
    )
    btn_exp.bind(on_release=self.exporter_zip)
    top_bar.add_widget(btn_exp)

    btn_imp = Button(
        text="Import ZIP", size_hint_x=0.28, background_color=(0.2, 0.6, 0.3, 1)
    )
    btn_imp.bind(on_release=self.ouvrir_import_zip)
    top_bar.add_widget(btn_imp)
    root.add_widget(top_bar)

    # --- ONGLETS ---
    tabs = TabbedPanel(do_default_tab=False, tab_width=160)

    # Onglet 1 : Recherche & Schéma
    tab_search = TabbedPanelItem(text="Rechercher")
    tab_search.add_widget(self.build_search_tab())
    tabs.add_widget(tab_search)

    # Onglet 2 : Ajouter
    tab_add = TabbedPanelItem(text="Ajouter")
    tab_add.add_widget(self.build_add_tab())
    tabs.add_widget(tab_add)

    root.add_widget(tabs)
    self.rechercher()
    return root

  def init_db(self):
    self.conn = sqlite3.connect(DB_PATH)
    self.c = self.conn.cursor()
    self.c.execute("""
            CREATE TABLE IF NOT EXISTS appareils (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marque TEXT,
                modele TEXT,
                carte TEXT,
                emmc TEXT,
                capacite TEXT,
                firmware_ref TEXT,
                pinout_imgs TEXT
            )
        """)
    self.conn.commit()

  # ================= ONGLET RECHERCHE =================
  def build_search_tab(self):
    layout = BoxLayout(orientation="vertical", spacing=6, padding=5)

    # Champs de filtrage rapides (2 colonnes pour tenir sur un écran mobile)
    grid = GridLayout(cols=2, size_hint_y=None, height=115, spacing=4)
    self.filters = {}
    champs = [
        ("Marque", "marque"),
        ("Modèle", "modele"),
        ("Carte", "carte"),
        ("eMMC", "emmc"),
        ("Capacité", "capacite"),
        ("Firmware Ref", "firmware_ref"),
    ]
    for hint, key in champs:
      ti = TextInput(hint_text=hint, multiline=False, font_size="13sp")
      ti.bind(text=lambda *args: self.rechercher())
      grid.add_widget(ti)
      self.filters[key] = ti
    layout.add_widget(grid)

    # Liste des résultats défilante
    scroll = ScrollView(size_hint_y=0.35)
    self.results_box = BoxLayout(
        orientation="vertical", size_hint_y=None, spacing=4
    )
    self.results_box.bind(minimum_height=self.results_box.setter("height"))
    scroll.add_widget(self.results_box)
    layout.add_widget(scroll)

    # Sélecteur si plusieurs photos Pinout
    self.spinner_imgs = Spinner(
        text="Sélectionner une fiche ci-dessus",
        size_hint_y=None,
        height=38,
    )
    self.spinner_imgs.bind(text=self.on_select_photo)
    layout.add_widget(self.spinner_imgs)

    # Zone d'affichage tactile zoomable du Pinout
    self.viewer = ZoomableImage(size_hint_y=0.65)
    layout.add_widget(self.viewer)

    return layout

  def rechercher(self):
    self.results_box.clear_widgets()
    query = (
        "SELECT id, marque, modele, carte, emmc, capacite, IFNULL(firmware_ref,"
        " ''), pinout_imgs FROM appareils WHERE 1=1"
    )
    params = []
    for key, ti in self.filters.items():
      val = ti.text.strip()
      if val:
        query += f" AND IFNULL({key}, '') LIKE ?"
        params.append(f"%{val}%")

    self.c.execute(query, params)
    for row in self.c.fetchall():
      item_id, marque, modele, carte, emmc, cap, fw, imgs = row
      titre = f"{marque} {modele} | {carte} | eMMC:{emmc} ({cap}) | FW:{fw}"
      btn = Button(
          text=titre,
          size_hint_y=None,
          height=44,
          font_size="12sp",
          halign="left",
      )
      btn.bind(on_release=lambda b, r=row: self.afficher_fiche(r))
      self.results_box.add_widget(btn)

  def afficher_fiche(self, row):
    imgs_str = row[7]
    if imgs_str:
      imgs = [i.strip() for i in imgs_str.split(";") if i.strip()]
      if imgs:
        self.spinner_imgs.values = imgs
        self.spinner_imgs.text = imgs[0]
        self.on_select_photo(self.spinner_imgs, imgs[0])
        return
    self.spinner_imgs.values = []
    self.spinner_imgs.text = "Aucune image Pinout"
    self.viewer.set_source("")

  def on_select_photo(self, spinner, img_name):
    path = os.path.join(IMG_DIR, img_name)
    if os.path.exists(path):
      self.viewer.set_source(path)

  # ================= ONGLET AJOUT =================
  def build_add_tab(self):
    layout = BoxLayout(orientation="vertical", spacing=8, padding=10)
    self.add_inputs = {}
    champs = [
        ("Marque *", "marque"),
        ("Modèle *", "modele"),
        ("Référence Carte", "carte"),
        ("Référence eMMC", "emmc"),
        ("Capacité (ex: 64 Go)", "capacite"),
        ("Firmware Ref", "firmware_ref"),
    ]
    for hint, key in champs:
      ti = TextInput(
          hint_text=hint, multiline=False, size_hint_y=None, height=42
      )
      layout.add_widget(ti)
      self.add_inputs[key] = ti

    self.lbl_photos = Label(
        text="Aucune photo sélectionnée", size_hint_y=None, height=30
    )
    btn_pick = Button(
        text="Choisir photo(s) depuis la galerie",
        size_hint_y=None,
        height=45,
    )
    btn_pick.bind(on_release=self.ouvrir_selecteur_photos)

    btn_save = Button(
        text="Enregistrer la fiche",
        size_hint_y=None,
        height=50,
        background_color=(0.1, 0.7, 0.3, 1),
    )
    btn_save.bind(on_release=self.enregistrer_fiche)

    layout.add_widget(btn_pick)
    layout.add_widget(self.lbl_photos)
    layout.add_widget(btn_save)
    layout.add_widget(Label())  # Espaceur
    return layout

  def ouvrir_selecteur_photos(self, instance):
    start_dir = (
        "/storage/emulated/0/Download"
        if platform == "android"
        else os.path.expanduser("~")
    )
    fc = FileChooserIconView(
        path=start_dir, filters=["*.png", "*.jpg", "*.jpeg", "*.webp"]
    )
    fc.multiselect = True
    box = BoxLayout(orientation="vertical")
    box.add_widget(fc)
    btn_ok = Button(text="Valider la sélection", size_hint_y=None, height=45)
    box.add_widget(btn_ok)
    popup = Popup(title="Sélectionner photos Pinout", content=box, size_hint=(0.95, 0.9))

    def valider(_):
      self.selected_photos = fc.selection
      self.lbl_photos.text = f"{len(self.selected_photos)} photo(s) choisie(s)"
      popup.dismiss()

    btn_ok.bind(on_release=valider)
    popup.open()

  def enregistrer_fiche(self, instance):
    marque = self.add_inputs["marque"].text.strip()
    modele = self.add_inputs["modele"].text.strip()
    carte = self.add_inputs["carte"].text.strip()
    emmc = self.add_inputs["emmc"].text.strip()
    capacite = self.add_inputs["capacite"].text.strip()
    firmware_ref = self.add_inputs["firmware_ref"].text.strip()

    if not marque or not modele:
      self.popup_msg("Erreur", "Marque et Modèle obligatoires.")
      return

    saved = []
    for path in self.selected_photos:
      dest_name = f"{marque}_{modele}_{os.path.basename(path)}".replace(" ", "_")
      dest_path = os.path.join(IMG_DIR, dest_name)
      shutil.copy2(path, dest_path)
      saved.append(dest_name)

    self.c.execute(
        "INSERT INTO appareils (marque, modele, carte, emmc, capacite,"
        " firmware_ref, pinout_imgs) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (marque, modele, carte, emmc, capacite, firmware_ref, ";".join(saved)),
    )
    self.conn.commit()

    for ti in self.add_inputs.values():
      ti.text = ""
    self.selected_photos = []
    self.lbl_photos.text = "Aucune photo sélectionnée"
    self.rechercher()
    self.popup_msg("Succès", "Fiche enregistrée !")

  # ================= IMPORT / EXPORT ZIP =================
  def exporter_zip(self, instance):
    out_dir = (
        "/storage/emulated/0/Download"
        if platform == "android"
        else BASE_DIR
    )
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    zip_path = os.path.join(out_dir, f"Export_Pinout_{date_str}.zip")
    try:
      self.conn.commit()
      with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_PATH):
          zf.write(DB_PATH, arcname="base_emmc.db")
        for f in os.listdir(IMG_DIR):
          fp = os.path.join(IMG_DIR, f)
          if os.path.isfile(fp):
            zf.write(fp, arcname=os.path.join("pinouts", f))
      self.popup_msg("Export réussi", f"Fichier enregistré dans :\n{zip_path}")
    except Exception as e:
      self.popup_msg("Erreur", str(e))

  def ouvrir_import_zip(self, instance):
    start_dir = (
        "/storage/emulated/0/Download"
        if platform == "android"
        else os.path.expanduser("~")
    )
    fc = FileChooserIconView(path=start_dir, filters=["*.zip"])
    box = BoxLayout(orientation="vertical")
    box.add_widget(fc)
    btn_ok = Button(text="Fusionner ce ZIP", size_hint_y=None, height=45)
    box.add_widget(btn_ok)
    popup = Popup(title="Importer ZIP", content=box, size_hint=(0.95, 0.9))

    def fusionner(_):
      if fc.selection:
        self.importer_zip(fc.selection[0])
      popup.dismiss()

    btn_ok.bind(on_release=fusionner)
    popup.open()

  def importer_zip(self, zip_path):
    temp_dir = os.path.join(BASE_DIR, "_temp_imp")
    if os.path.exists(temp_dir):
      shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)
    try:
      with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)
      ext_db = os.path.join(temp_dir, "base_emmc.db")
      ext_img = os.path.join(temp_dir, "pinouts")
      if not os.path.exists(ext_db):
        self.popup_msg("Erreur", "ZIP invalide.")
        return

      ext_conn = sqlite3.connect(ext_db)
      ext_c = ext_conn.cursor()
      ext_c.execute(
          "SELECT marque, modele, carte, emmc, capacite, firmware_ref,"
          " pinout_imgs FROM appareils"
      )
      ajoutes = 0
      for marque, modele, carte, emmc, cap, fw, imgs in ext_c.fetchall():
        self.c.execute(
            "SELECT id FROM appareils WHERE marque=? AND modele=? AND carte=? AND emmc=?",
            (marque, modele, carte, emmc),
        )
        if self.c.fetchone():
          continue
        new_imgs = []
        if imgs:
          for im in imgs.split(";"):
            src = os.path.join(ext_img, im.strip())
            if os.path.exists(src):
              shutil.copy2(src, os.path.join(IMG_DIR, im.strip()))
              new_imgs.append(im.strip())
        self.c.execute(
            "INSERT INTO appareils (marque, modele, carte, emmc, capacite,"
            " firmware_ref, pinout_imgs) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (marque, modele, carte, emmc, cap, fw, ";".join(new_imgs)),
        )
        ajoutes += 1
      self.conn.commit()
      ext_conn.close()
      self.rechercher()
      self.popup_msg("Fusion terminée", f"{ajoutes} nouvelle(s) fiche(s) ajoutée(s) !")
    except Exception as e:
      self.popup_msg("Erreur", str(e))
    finally:
      if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

  def popup_msg(self, title, msg):
    Popup(
        title=title,
        content=Label(text=msg),
        size_hint=(0.85, 0.35),
    ).open()


if __name__ == "__main__":
  PinoutMobileApp().run()