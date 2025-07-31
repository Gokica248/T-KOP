from flask import Flask, render_template, request, redirect, url_for, flash, session
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'tajni_kljuc'  # Promijeni po potrebi

DATA_FILE = 'podaci.json'


def ucitaj_podatke():
    """Učitava podatke iz JSON datoteke."""
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def spremi_podatke(podaci):
    """Sprema podatke u JSON datoteku."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(podaci, f, indent=2, ensure_ascii=False)


def login_required(rola):
    """Dekorator za provjeru uloge korisnika."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'korisnik' not in session:
                return redirect(url_for('login'))
            if session.get('uloga') != rola:
                flash('Nemate pristup ovoj stranici.')
                return redirect(url_for('login'))
            return f(*args, **kwargs)

        return wrapper

    return decorator


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Ruta za prijavu korisnika."""
    if request.method == 'POST':
        korime = request.form['korime']
        lozinka = request.form['lozinka']

        podaci = ucitaj_podatke()
        korisnik = next((k for k in podaci['korisnici'] if k['korime'] == korime and k['lozinka'] == lozinka), None)

        if korisnik:
            session['korisnik'] = korisnik['korime']
            session['uloga'] = korisnik['uloga']
            if korisnik['uloga'] == 'vlasnik':
                return redirect(url_for('vlasnik_dashboard'))
            else:
                return redirect(url_for('radnik_dashboard'))
        else:
            flash('Neispravno korisničko ime ili lozinka.')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Ruta za odjavu korisnika."""
    session.clear()
    return redirect(url_for('login'))


@app.route('/vlasnik', methods=['GET', 'POST'])
@login_required('vlasnik')
def vlasnik_dashboard():
    """Dashboard za vlasnika - dodavanje zadataka."""
    podaci = ucitaj_podatke()
    radnici = [k for k in podaci['korisnici'] if k['uloga'] == 'radnik']

    if request.method == 'POST':
        korisnik = request.form.get('korisnik')
        naziv = request.form.get('naziv')
        opis = request.form.get('opis')
        datum = request.form.get('datum')
        vrijeme = request.form.get('vrijeme')
        mjesto = request.form.get('mjesto')

        # Ispravljeno: uzimamo vrijednost iz polja 'mjesto' za lokaciju
        lokacija = mjesto

        if not korisnik or not naziv:
            flash('Morate odabrati radnika i unijeti naziv zadatka.')
            return redirect(url_for('vlasnik_dashboard'))

        radnik = next((r for r in radnici if r['korime'] == korisnik), None)
        if radnik is None:
            flash('Odabrani radnik ne postoji.')
            return redirect(url_for('vlasnik_dashboard'))

        novi_zadatak = {
            'naziv': naziv,
            'opis': opis,
            'datum': datum,
            'vrijeme': vrijeme,
            'mjesto': mjesto,
            'status': 'NEODRAĐENO',
            'ocjena': 0,
            'opis_ocjene': '',
            'opis_zasto_nije': '',
            'radni_sati': 0,
            'lokacija': lokacija if lokacija else ""
        }

        radnik.setdefault('zadaci', []).append(novi_zadatak)
        spremi_podatke(podaci)

        # Šaljemo poruku u template umjesto flash+redirect
        return render_template('vlasnik.html', radnici=radnici, poruka="Zadatak je uspješno dodan.")

    return render_template('vlasnik.html', radnici=radnici)


@app.route('/vlasnik/radnik/<korisnik>', methods=['GET', 'POST'])
@login_required('vlasnik')
def vlasnik_pregled_radnika(korisnik):
    """Pregled zadataka za specifičnog radnika od strane vlasnika."""
    podaci = ucitaj_podatke()
    radnik = next((k for k in podaci['korisnici'] if k['korime'] == korisnik and k['uloga'] == 'radnik'), None)
    if radnik is None:
        flash('Radnik ne postoji.')
        return redirect(url_for('vlasnik_dashboard'))

    if request.method == 'POST':
        if 'obrisi' in request.form:
            indeks = int(request.form.get('indeks_za_brisanje'))
            if 0 <= indeks < len(radnik.get('zadaci', [])):
                zadatak_za_brisanje = radnik['zadaci'].pop(indeks)
                spremi_podatke(podaci)
                flash(f'Zadatak "{zadatak_za_brisanje["naziv"]}" je obrisan.')
            else:
                flash('Neispravan indeks zadatka za brisanje.')
            return redirect(url_for('vlasnik_pregled_radnika', korisnik=korisnik))
        else:
            indeks = int(request.form.get('indeks'))
            ocjena = int(request.form.get('ocjena'))
            opis_ocjene = request.form.get('opis_ocjene', '').strip()

            zadatak = radnik['zadaci'][indeks]
            if zadatak['status'] != 'ODRAĐENO':
                flash('Ocjenu možete dati samo za odrađene zadatke.')
                return redirect(url_for('vlasnik_pregled_radnika', korisnik=korisnik))

            zadatak['ocjena'] = ocjena
            zadatak['opis_ocjene'] = opis_ocjene
            spremi_podatke(podaci)
            flash('Ocjena i opis uspješno spremljeni.')
            return redirect(url_for('vlasnik_pregled_radnika', korisnik=korisnik))

    return render_template('vlasnik_pregled_radnika.html', radnik=radnik)


@app.route('/radnik')
@login_required('radnik')
def radnik_dashboard():
    """Dashboard za radnika - prikaz zadataka."""
    podaci = ucitaj_podatke()
    radnik = next((k for k in podaci['korisnici'] if k['korime'] == session['korisnik']), None)
    if radnik is None:
        flash('Došlo je do greške.')
        return redirect(url_for('logout'))

    return render_template('radnik.html', radnik=radnik)


@app.route('/radnik/zadatak/<int:indeks>', methods=['GET', 'POST'])
@login_required('radnik')
def radnik_zadatak(indeks):
    """Prikaz i ažuriranje statusa pojedinog zadatka od strane radnika."""
    podaci = ucitaj_podatke()
    radnik = next((k for k in podaci['korisnici'] if k['korime'] == session['korisnik']), None)
    if radnik is None or indeks < 0 or indeks >= len(radnik.get('zadaci', [])):
        flash('Zadatak ne postoji.')
        return redirect(url_for('radnik_dashboard'))

    zadatak = radnik['zadaci'][indeks]

    if request.method == 'POST':
        novi_status = request.form.get('status')
        radni_sati = request.form.get('radni_sati')
        opis_zasto_nije = request.form.get('opis_zasto_nije', '').strip()

        if novi_status not in ['NEODRAĐENO', 'U TOKU', 'ODRAĐENO']:
            flash('Neispravan status zadatka.')
            return redirect(url_for('radnik_zadatak', indeks=indeks))

        zadatak['status'] = novi_status

        try:
            zadatak['radni_sati'] = float(radni_sati)
        except (ValueError, TypeError):
            zadatak['radni_sati'] = 0

        if novi_status == 'NEODRAĐENO':
            zadatak['opis_zasto_nije'] = opis_zasto_nije
            zadatak['ocjena'] = 0
        else:
            zadatak['opis_zasto_nije'] = ''
            # Ocjena se ne mijenja ovdje, već to radi vlasnik
            pass

        spremi_podatke(podaci)
        flash('Podaci uspješno spremljeni.')
        return redirect(url_for('radnik_zadatak', indeks=indeks))

    return render_template('radnik_zadatak.html', zadatak=zadatak, indeks=indeks)


@app.route('/vlasnik/radnici', methods=['GET', 'POST'])
@login_required('vlasnik')
def vlasnik_upravljanje_radnicima():
    """Upravljanje radnicima od strane vlasnika (dodavanje, brisanje, uređivanje)."""
    podaci = ucitaj_podatke()
    radnici = [k for k in podaci['korisnici'] if k['uloga'] == 'radnik']

    if request.method == 'POST':
        if 'dodaj' in request.form:
            novo_korime = request.form.get('novo_korime', '').strip()
            nova_lozinka = request.form.get('nova_lozinka', '').strip()
            if not novo_korime or not nova_lozinka:
                flash('Unesite korisničko ime i lozinku za novog radnika.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            if any(k['korime'] == novo_korime for k in podaci['korisnici']):
                flash('Korisničko ime već postoji.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            novi_radnik = {
                'korime': novo_korime,
                'lozinka': nova_lozinka,
                'uloga': 'radnik',
                'zadaci': [],
                'lokacija': {"lat": 0, "lng": 0}
            }
            podaci['korisnici'].append(novi_radnik)
            spremi_podatke(podaci)
            flash(f'Radnik "{novo_korime}" uspješno dodan.')
            return redirect(url_for('vlasnik_upravljanje_radnicima'))

        elif 'obrisi' in request.form:
            korime_za_brisanje = request.form.get('korime_za_brisanje')
            if korime_za_brisanje:
                podaci['korisnici'] = [k for k in podaci['korisnici'] if k['korime'] != korime_za_brisanje]
                spremi_podatke(podaci)
                flash(f'Radnik "{korime_za_brisanje}" je obrisan.')
            else:
                flash('Neispravan radnik za brisanje.')
            return redirect(url_for('vlasnik_upravljanje_radnicima'))

        elif 'uredi' in request.form:
            stari_korime = request.form.get('stari_korime')
            novi_korime = request.form.get('novi_korime', '').strip()
            nova_lozinka = request.form.get('nova_lozinka', '').strip()

            if not novi_korime or not nova_lozinka:
                flash('Morate unijeti novo korisničko ime i lozinku.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            if stari_korime is None:
                flash('Neispravan radnik za uređivanje.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            if novi_korime != stari_korime and any(k['korime'] == novi_korime for k in podaci['korisnici']):
                flash('Novo korisničko ime već postoji.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            radnik = next((k for k in podaci['korisnici'] if k['korime'] == stari_korime and k['uloga'] == 'radnik'),
                          None)
            if radnik is None:
                flash('Radnik ne postoji.')
                return redirect(url_for('vlasnik_upravljanje_radnicima'))

            radnik['korime'] = novi_korime
            radnik['lozinka'] = nova_lozinka
            spremi_podatke(podaci)
            flash('Podaci radnika su uspješno ažurirani.')
            return redirect(url_for('vlasnik_upravljanje_radnicima'))

    return render_template('vlasnik_upravljanje_radnicima.html', radnici=radnici)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
