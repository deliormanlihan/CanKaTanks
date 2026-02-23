import flet as ft
import os
import json
import webbrowser
from datetime import datetime

def main(page: ft.Page):
    # ================= HAFIZA SİSTEMİ =================
    appdata_yolu = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'CanKaSoundingMobil')
    os.makedirs(appdata_yolu, exist_ok=True)
    ayarlar_dosyasi = os.path.join(appdata_yolu, "ayarlar.json")
    
    ayarlar = {
        "tema": "dark",
        "konum": "ELEUSIS",
        "ce": "Meriç Demirci",
        "trim": "-0.5",
        "tanklar": {}
    }
    
    if os.path.exists(ayarlar_dosyasi):
        try:
            with open(ayarlar_dosyasi, "r", encoding="utf-8") as f:
                ayarlar.update(json.load(f))
        except: pass

    def ayarlari_kaydet():
        try:
            with open(ayarlar_dosyasi, "w", encoding="utf-8") as f:
                json.dump(ayarlar, f, ensure_ascii=False, indent=4)
        except: pass

    # --- EKRAN AYARLARI ---
    page.title = "CAN KA Sounding"
    page.theme_mode = ft.ThemeMode.LIGHT if ayarlar["tema"] == "light" else ft.ThemeMode.DARK
    page.scroll = ft.ScrollMode.AUTO 
    page.padding = 15

    # ================= JSON VERİ YÜKLEME (EXCEL YERİNE) =================
    veri_tablolari = {}
    if os.path.exists("Tanklar.json"):
        with open("Tanklar.json", "r", encoding="utf-8") as f:
            veri_tablolari = json.load(f)
    else:
        print("DİKKAT: Tanklar.json bulunamadı!")

    # --- BİLGİ KUTULARI ---
    txt_tarih = ft.TextField(label="Tarih", value=datetime.now().strftime("%d.%m.%Y"), width=120, text_align=ft.TextAlign.CENTER)
    txt_saat = ft.TextField(label="Saat", value=datetime.now().strftime("%H:%M"), width=100, text_align=ft.TextAlign.CENTER)

    def oto_format_tarih(e):
        val = "".join(filter(str.isdigit, txt_tarih.value))
        yeni = ""
        if len(val) > 0: yeni += val[:2]
        if len(val) > 2: yeni += "." + val[2:4]
        if len(val) > 4: yeni += "." + val[4:8]
        if txt_tarih.value != yeni: txt_tarih.value = yeni; page.update()

    def oto_format_saat(e):
        val = "".join(filter(str.isdigit, txt_saat.value))
        yeni = ""
        if len(val) > 0: yeni += val[:2]
        if len(val) > 2: yeni += ":" + val[2:4]
        if txt_saat.value != yeni: txt_saat.value = yeni; page.update()

    txt_tarih.on_change = oto_format_tarih
    txt_saat.on_change = oto_format_saat

    txt_konum = ft.TextField(label="Konum", value=ayarlar["konum"], expand=True)
    txt_ce = ft.TextField(label="Başmühendis", value=ayarlar["ce"], expand=True)
    txt_trim = ft.TextField(label="Trim (m)", value=ayarlar["trim"], width=100, text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER)

    def tema_degistir(e):
        page.theme_mode = ft.ThemeMode.LIGHT if switch_tema.value else ft.ThemeMode.DARK
        ayarlar["tema"] = "light" if switch_tema.value else "dark"
        ayarlari_kaydet(); page.update()

    switch_tema = ft.Switch(label="Light Mode", value=(page.theme_mode == ft.ThemeMode.LIGHT), on_change=tema_degistir)
    page.appbar = ft.AppBar(title=ft.Text("DAILY BUNKER REPORT", weight=ft.FontWeight.BOLD), center_title=True, bgcolor="surfaceVariant", actions=[switch_tema, ft.Container(width=10)])

    # ================= SAFKAN PYTHON MATEMATİK MOTORU =================
    def get_trim_indices(trim_hedef, trims):
        if trims[0] > trims[-1]: t_clamp = max(min(trim_hedef, trims[0]), trims[-1])
        else: t_clamp = max(min(trim_hedef, trims[-1]), trims[0])
        
        diffs = [(abs(t - t_clamp), i) for i, t in enumerate(trims)]
        diffs.sort(key=lambda x: x[0])
        idx1, idx2 = diffs[0][1], diffs[1][1]
        if idx1 > idx2: idx1, idx2 = idx2, idx1
        return idx1, idx2, t_clamp

    class MobilTankSatiri:
        def __init__(self, tank_adi, max_kapasite, sayfa_adi, guncelle_callback):
            self.tank_adi = tank_adi
            self.max_kapasite = max_kapasite
            self.tablo = veri_tablolari.get(sayfa_adi)
            self.guncelle_callback = guncelle_callback
            self.guncel_hacim = 0.0
            self._is_updating = False

            self.snd_input = ft.TextField(label="cm", width=90, text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER, on_change=self.hesapla_tetik)
            self.vol_input = ft.TextField(label="m³", width=110, text_align=ft.TextAlign.CENTER, keyboard_type=ft.KeyboardType.NUMBER, color="blue", on_change=self.hesapla_ters_tetik)
            self.pct_label = ft.Text("% 0.0", size=15, weight=ft.FontWeight.BOLD, color="grey")

            eski = ayarlar["tanklar"].get(self.tank_adi, {})
            if "snd" in eski and eski["snd"]: self.snd_input.value = eski["snd"]
            if "vol" in eski and eski["vol"]: self.vol_input.value = eski["vol"]

            self.view = ft.Container(
                content=ft.Column([
                    ft.Text(f"{self.tank_adi} (Max: {self.max_kapasite:.3f} m³)", weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([self.snd_input, self.vol_input, self.pct_label], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ]), padding=12, bgcolor="surfaceVariant", border_radius=10, margin=ft.Margin(0, 5, 0, 5)
            )

        def bilinear(self, trim_hedef, snd_hedef):
            if not self.tablo: return 0.0
            snd_arr, trm_arr, val_arr = self.tablo["soundings"], self.tablo["trims"], self.tablo["values"]
            
            if snd_hedef <= snd_arr[0]: snd_hedef = snd_arr[0]
            elif snd_hedef >= snd_arr[-1]: snd_hedef = snd_arr[-1]
            
            s_idx1, s_idx2 = 0, 1
            for i in range(len(snd_arr)-1):
                if snd_arr[i] <= snd_hedef <= snd_arr[i+1]:
                    s_idx1, s_idx2 = i, i+1
                    break
                    
            t_idx1, t_idx2, t_clamp = get_trim_indices(trim_hedef, trm_arr)
            
            s1, s2, t1, t2 = snd_arr[s_idx1], snd_arr[s_idx2], trm_arr[t_idx1], trm_arr[t_idx2]
            v11, v12 = val_arr[s_idx1][t_idx1], val_arr[s_idx1][t_idx2]
            v21, v22 = val_arr[s_idx2][t_idx1], val_arr[s_idx2][t_idx2]
            
            s_rat = 0 if s2 == s1 else (snd_hedef - s1) / (s2 - s1)
            t_rat = 0 if t2 == t1 else (t_clamp - t1) / (t2 - t1)
            
            return (v11 * (1 - t_rat) + v12 * t_rat) * (1 - s_rat) + (v21 * (1 - t_rat) + v22 * t_rat) * s_rat

        def reverse(self, trim_hedef, vol_hedef):
            if not self.tablo: return 0.0
            snd_arr, trm_arr, val_arr = self.tablo["soundings"], self.tablo["trims"], self.tablo["values"]
            
            t_idx1, t_idx2, t_clamp = get_trim_indices(trim_hedef, trm_arr)
            t1, t2 = trm_arr[t_idx1], trm_arr[t_idx2]
            t_rat = 0 if t2 == t1 else (t_clamp - t1) / (t2 - t1)
            
            sanal_hacimler = [val_arr[i][t_idx1] * (1 - t_rat) + val_arr[i][t_idx2] * t_rat for i in range(len(snd_arr))]
            
            if vol_hedef <= sanal_hacimler[0]: return snd_arr[0]
            if vol_hedef >= sanal_hacimler[-1]: return snd_arr[-1]
            
            r_idx1, r_idx2 = 0, 1
            for i in range(len(sanal_hacimler)-1):
                if sanal_hacimler[i] <= vol_hedef <= sanal_hacimler[i+1]:
                    r_idx1, r_idx2 = i, i+1
                    break
                    
            v1, v2 = sanal_hacimler[r_idx1], sanal_hacimler[r_idx2]
            v_rat = 0 if v2 == v1 else (vol_hedef - v1) / (v2 - v1)
            return snd_arr[r_idx1] * (1 - v_rat) + snd_arr[r_idx2] * v_rat

        def hesapla_tetik(self, e=None):
            if self._is_updating: return
            try:
                snd_t, trim_t = (self.snd_input.value or "").replace(',', '.'), (txt_trim.value or "0.0").replace(',', '.')
                if not snd_t:
                    self._is_updating = True; self.guncel_hacim = 0.0; self.vol_input.value = ""; self.pct_label.value = "% 0.0"; self.pct_label.color = "grey"; self._is_updating = False; self.guncelle_callback(); page.update(); return
                hacim = max(0, self.bilinear(float(trim_t), float(snd_t)))
                self.guncel_hacim = hacim
                self._is_updating = True; self.vol_input.value = f"{hacim:.4f}"; self._is_updating = False
                self._yuzde_guncelle(hacim)
            except ValueError: pass
            finally: self.guncelle_callback(); page.update()

        def hesapla_ters_tetik(self, e=None):
            if self._is_updating: return
            try:
                vol_t, trim_t = (self.vol_input.value or "").replace(',', '.'), (txt_trim.value or "0.0").replace(',', '.')
                if not vol_t:
                    self._is_updating = True; self.guncel_hacim = 0.0; self.snd_input.value = ""; self.pct_label.value = "% 0.0"; self.pct_label.color = "grey"; self._is_updating = False; self.guncelle_callback(); page.update(); return
                vol = float(vol_t)
                snd = max(0, self.reverse(float(trim_t), vol))
                self.guncel_hacim = vol
                self._is_updating = True; self.snd_input.value = f"{snd:.1f}"; self._is_updating = False
                self._yuzde_guncelle(vol)
            except ValueError: pass
            finally: self.guncelle_callback(); page.update()

        def _yuzde_guncelle(self, hacim):
            y = (hacim / self.max_kapasite) * 100 if self.max_kapasite > 0 else 0
            self.pct_label.value, self.pct_label.color = f"% {y:.1f}", ("red" if y > 70 else "orange" if y > 50 else "green")

        def veriyi_kaydet(self): ayarlar["tanklar"][self.tank_adi] = {"snd": self.snd_input.value, "vol": self.vol_input.value}

    # --- LİSTELER VE HESAPLAMALAR ---
    sl_nesneleri, bl_nesneleri = [], []
    sl_kapasite = 7.40 + 11.50 + 0.40 + 1.000
    lbl_sl_toplam = ft.Text("Toplam Sludge: 0.0000 m³  |  % 0.0", weight=ft.FontWeight.BOLD, color="black")

    def toplamlari_guncelle():
        th = sum(t.guncel_hacim for t in sl_nesneleri)
        lbl_sl_toplam.value = f"Toplam Sludge: {th:.4f} m³  |  % {(th/sl_kapasite)*100 if sl_kapasite > 0 else 0:.1f}"
        ayarlar["konum"], ayarlar["ce"], ayarlar["trim"] = txt_konum.value, txt_ce.value, txt_trim.value
        for t in sl_nesneleri + bl_nesneleri: t.veriyi_kaydet()
        ayarlari_kaydet()

    def tumunu_hesapla(e):
        for t in sl_nesneleri + bl_nesneleri:
            if t.snd_input.value: t.hesapla_tetik()
            elif t.vol_input.value: t.hesapla_ters_tetik()
        page.update()

    txt_trim.on_change = tumunu_hesapla

    sl_veri = [("Oily Bilge Tank", 7.40, "Oily Bilge Tank"), ("Sludge Tank", 11.50, "Sludge Tank"), ("M/E Scavenge Box Drain Tank", 0.40, "Scavenge Tank"), ("Incinerator Waste Oil Tank", 1.000, "Incinerator Tank")]
    for a, k, s in sl_veri: sl_nesneleri.append(MobilTankSatiri(a, k, s, toplamlari_guncelle))
    bl_nesneleri.append(MobilTankSatiri("Bilge Holding Tank", 39.11, "Bilge Holding Tank", toplamlari_guncelle))

    def rapor_yazdir(e):
        html = f"<html><body style='font-family: Arial; margin: 30px;'><h2 style='text-align:center;'>M/T CAN KA<br>DAILY BUNKER REPORT</h2><p><b>Date/Time:</b> {txt_tarih.value} - {txt_saat.value}<br><b>Location:</b> {txt_konum.value}<br><b>Trim:</b> {txt_trim.value} m</p><table style='width:100%; border-collapse: collapse;' border='1'><tr><th style='background:#eee;'>Sludge Tanks</th><th>Capacity</th><th>Sounding</th><th>Volume</th><th>Fill</th></tr>"
        tv = 0
        for t in sl_nesneleri: html += f"<tr><td>{t.tank_adi}</td><td>{t.max_kapasite:.3f}</td><td>{t.snd_input.value or '-'}</td><td>{t.vol_input.value or '-'}</td><td>{t.pct_label.value}</td></tr>"; tv += t.guncel_hacim
        html += f"<tr style='background:#fff3cd; font-weight:bold;'><td colspan='3' align='right'>TOTAL:</td><td>{tv:.4f}</td><td>-</td></tr></table><br><table style='width:100%; border-collapse: collapse;' border='1'><tr><th style='background:#eee;'>Bilge Tanks</th><th>Capacity</th><th>Sounding</th><th>Volume</th><th>Fill</th></tr>"
        for t in bl_nesneleri: html += f"<tr><td>{t.tank_adi}</td><td>{t.max_kapasite:.3f}</td><td>{t.snd_input.value or '-'}</td><td>{t.vol_input.value or '-'}</td><td>{t.pct_label.value}</td></tr>"
        html += f"</table><div style='margin-top:50px; text-align:right;'><b>Chief Engineer</b><br>{txt_ce.value}</div><script>window.onload=function(){{window.print();}}</script></body></html>"
        try:
            with open("Report.html", "w", encoding="utf-8") as f: f.write(html)
            webbrowser.open('file://' + os.path.realpath("Report.html"))
        except: pass

    page.add(
        ft.Row([txt_tarih, txt_saat], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Row([txt_konum, txt_trim], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), txt_ce, ft.Divider(),
        ft.Text("SLUDGE TANKLARI", color="red", weight=ft.FontWeight.BOLD), *[t.view for t in sl_nesneleri], ft.Container(content=lbl_sl_toplam, bgcolor="orange", padding=15, border_radius=10, alignment=ft.Alignment(0,0)),
        ft.Divider(), ft.Text("BILGE TANKLARI", color="blue", weight=ft.FontWeight.BOLD), *[t.view for t in bl_nesneleri],
        ft.Divider(), ft.ElevatedButton("🖨️ RAPORU YAZDIR", bgcolor="purple", color="white", height=50, on_click=rapor_yazdir, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))),
        ft.Container(height=10), ft.Text("Developed By Deliormanlıhan Meriç DEMİRCİ", color="green", italic=True, size=12, weight=ft.FontWeight.BOLD)
    )
    tumunu_hesapla(None)

ft.run(main)
