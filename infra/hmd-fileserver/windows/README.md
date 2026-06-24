# Connexion aux lecteurs réseau HMD (postes Windows)

Serveur de fichiers : **`\\192.168.1.4`**

## Méthode la plus simple : les scripts `.bat`

Copiez le script correspondant à votre profil sur le poste, puis **double-cliquez** dessus.
Il vous demandera votre identifiant puis votre mot de passe (une seule fois).

| Profil | Script | Lecteurs montés |
|---|---|---|
| Admin (Samir, Aziz) | `profil-admin.bat` | `H:` tout HMD · `T:` IT · `P:` Partage |
| Comptable / Gestion (Anissa) | `profil-comptable.bat` | `S:` Support · `P:` Partage · `D:` Dépôt |
| Élevage (Amen Allah, Siwar) | `profil-elevage.bat` | `E:` Élevage · `P:` Partage · `D:` Dépôt |
| Prod. Végétale (Yassine) | `profil-vegetale.bat` | `V:` Végétale · `P:` Partage · `D:` Dépôt |
| Fromagerie (Tawfiq) | `profil-fromagerie.bat` | `F:` Fromagerie · `P:` Partage · `D:` Dépôt |
| Invité (Ridha / anonyme) | `profil-invite.bat` | `P:` Partage + dépôts |
| Tout le staff | `monter-HMD.bat` | `H:` tout votre espace · `P:` Partage |

> Avec le lecteur **`H:` (racine HMD)**, vous ne voyez que les dossiers auxquels
> vous avez droit — les autres sont automatiquement masqués.

### Lancer automatiquement à l'ouverture de session (optionnel)
1. Touche **Windows + R**, tapez `shell:startup`, Entrée.
2. Copiez-y un **raccourci** vers votre script `.bat`.

---

## Méthode manuelle (explorateur Windows)

Clic droit sur « Ce PC » → **Connecter un lecteur réseau** :
- Dossier : `\\192.168.1.4\HMD` (ou un partage précis : `\\192.168.1.4\Support`)
- Cochez **« Se connecter à l'aide d'informations d'identification différentes »**

> **PIÈGE IMPORTANT — format du nom d'utilisateur**
> Dans le champ identifiant, ne tapez **pas** `anissa` seul (Windows croit que
> c'est un compte local du PC). Tapez :
>
> ```
> 192.168.1.4\anissa
> ```
>
> Le préfixe `192.168.1.4\` force Windows à utiliser le compte **du serveur**.

---

## En cas de problème

### « Vous n'avez pas l'autorisation d'accéder »
Windows a mis en cache une mauvaise connexion. Ouvrez **CMD** (touche Windows →
tapez `cmd`) et exécutez :

```cmd
net use * /delete /y
cmdkey /list
```

S'il existe une entrée pour `192.168.1.4`, supprimez-la :
```cmd
cmdkey /delete:192.168.1.4
```
Puis relancez votre script `.bat`.

### « System error 1219 » (connexions multiples)
Windows interdit deux connexions au même serveur avec des comptes différents.
Purgez avant de changer d'utilisateur :
```cmd
net use * /delete /y
```

### Connexion en ligne de commande (toujours fiable)
```cmd
net use H: \\192.168.1.4\HMD /user:VOTRE_LOGIN *
```
Le `*` final fait demander le mot de passe.

---

## Identifiants

Votre identifiant = votre prénom en minuscules (ex : `anissa`, `yassine`,
`amen_allah`). Les mots de passe initiaux sont fournis par l'administrateur
(fichier `/root/hmd-smb-credentials.txt` sur le serveur). Changez-le dès la
première connexion si possible.
