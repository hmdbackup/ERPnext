# Réunion finance — 26/08/2026, présentation des maquettes à M. Samir

> Transcription traduite en français. L'audio mélange français et derja
> tunisienne : les passages en derja sont restitués au sens, pas au mot.
> Quelques segments sont abîmés (phrases fusionnées, fin de réunion tronquée) —
> ils sont laissés tels quels et signalés dans `compte_rendu.md`.

---

**Développeur :** Enregistrer... J'espère que je pourrai car je n'ai pas beaucoup de stockage. Enregistrer... « Non disponible pour les personnes d'une organisation différente ». Bon... voilà, j'ai mis sur le côté... l'enregistrement du micro.

**Si Samir :** D'accord, c'est bon...

**Développeur :** Regarde de ton côté si quelqu'un peut le faire, car vous ne faites pas partie de l'organisation de mon compte.

**Si Samir :** Ok, ça marche.

**Développeur :** J'ai mis de mon côté... un enregistrement audio... c'est tout. Après, je t'enverrai un récap... sur Teams, sur WhatsApp ou autre. Bien... Donc maintenant, je vais te présenter les maquettes des 3 *User Stories* que j'ai sélectionnées... et dans lesquelles tu m'avais déjà montré à l'époque quelques décisions que tu avais prises... et il y a des décisions que tu as prises qui ont fait que j'ai créé... une maquette supplémentaire. Bien... Donc le problème principal (c'est-à-dire dans notre *User Story*) est que le coût du litre qu'on a affiché était faux. Maintenant je l'ai corrigé... avec tes décisions bien sûr, car il y a des logiques métier, c'est-à-dire...

**Si Samir :** Ok, d'accord, ok.

**Développeur :** Bien... Nous avons 3 écrans... c'est-à-dire l'écran « charge par atelier et coût du litre », l'écran « parc et intervention », et un 3ème écran que tu n'as pas vu avec moi la dernière fois... qui est « production laitière ».

Bien... Dans le premier écran, ça veut dire... (Combien coûte réellement un litre de lait et qu'est-ce qu'on a le droit de mettre dedans)... et dans « parc et intervention » on se pose la question (dans quel état est le matériel, ce que coûte son entretien et est-ce que la comptabilité dit la même chose)... et dans « production laitière »... (combien de lait et lequel des deux comptages fait référence).

Bien... Pour la première *User Story*... c'est sous forme de rapport, c'est-à-dire un rapport de performance... où nous avons toutes les charges, par atelier... ça commence, ça veut dire...

**Si Samir :** Ouais je ne peux pas lire ça... tu peux agrandir un peu ?

**Développeur :** Excuse-moi... Comme ça, ça va ? Comme ça, ça va ou j'agrandis encore ?

**Si Samir :** Bien, non non c'est bon. Ok donc ça c'est la date... Donc euh... bien, en haut c'est... par atelier... ici les charges ventilées par atelier, puis le coût du lait poste par poste ou rapprochement comptable. Ok bien. Donc la date, ça c'est la date du rapport, c'est ça ? Ça veut dire...

**Développeur :** Oui.

**Si Samir :** Parce qu'aujourd'hui, si je viens faire un rapport... je mets que ce sera le 26/8, c'est ça ? Ah ok. Ou bien c'est la date du mois... la période c'est le mois, c'est ça ? C'est quoi les périodes ici ?

**Développeur :** Cette période est par mois... ça veut dire, comme tu l'as vu, si tu mets la date [segment abîmé] j'ai compris, je dois mettre la fin du mois, ou n'importe quel jour de ce mois-là, ou bien...

**Développeur :** N'importe quel jour du mois. Comme... comme tu me l'as dit la dernière fois.

**Si Samir :** Par exemple, si demain je mets le 15 juillet et que je choisis « mois », ça sera le mois de juillet entier ou le mois allant du 15 juin au 15 juillet ?

**Développeur :** Ça sera le mois allant du 15 juin au 15 juillet.

**Si Samir :** Je t'ai compris... Juste, excuse-moi, je pose ces questions-là car après, quand on va appliquer, on sera amenés à mettre ces dates-là, tu comprends... Donc cette période-là, est-elle gérée par tranches de 30 jours ou par mois calendaire ? Tu comprends pourquoi je pose la question... Ça veut dire que si tu dois faire du 15 juillet au 15 août par exemple... ou si tu mets n'importe quelle date dans le mois... ça donne le mois de... Quand on met « mensuel », c'est-à-dire une période mensuelle, quelles sont les périodes que tu as ? Dans les périodes, quelles sont les options dont tu disposes ?

**Développeur :** Je ne t'ai pas compris... ah... c'est-à-dire les... ah il y a... il y a par jour et il y a par semaine.

**Si Samir :** Donc la période, c'est soit un rapport d'un mois, soit d'une semaine, soit d'un jour, c'est bien ça ?

**Développeur :** Oui.

**Si Samir :** Ok donc si on met... euh... Donc dans ces cas-là, notre delta ici... c'est juste... c'est une date, ok...

**Développeur :** Mhm.

**Si Samir :** D'accord... une date a... donc si tu mets une date à gauche... pour le rapport du jour, ça sera de ce jour-là, ok ?

**Développeur :** Oui.

**Si Samir :** Bien, la semaine, ce sera la semaine à laquelle appartient cette date.

**Développeur :** Oui.

**Si Samir :** Ça veut dire que quand tu demandes à Excel, si tu as une date, il te retourne la semaine, ok ?

**Développeur :** Mhm.

**Si Samir :** Ok... je t'ai compris, c'est clair. Et le mois, le rapport du mois c'est le mois calendaire. C'est-à-dire que si tu mets le 15 juillet, ça sera le rapport de juillet... tu n'as pas besoin d'avoir la date du dernier jour... ouais... tu as compris ?

**Développeur :** Mhm. D'accord.

**Si Samir :** Oui... et quand on a notre delta ici... c'est juste... quand ce n'est pas imputé... ça devient un tiret comme ça pour ne pas mettre 0, car 0... C'est quoi « M-1 », ça c'est le mois d'avant, c'est ça ?

**Développeur :** Euh... je ne te comprends pas, de quoi parles-tu... ah... oui oui...

**Si Samir :** Ah, en haut tu as indicateur, valeur, unité, M-1, c'est la valeur du mois d'avant, c'est bien ça ? Ou de la semaine, de la semaine d'avant... ça c'est le delta.

**Développeur :** Oui... et si je fais une période journalière, ça sera le jour d'avant.

**Si Samir :** Donc c'est très bien comme ça, il n'y a aucun problème. C'est clair. Bien... pour ce delta, on est d'accord, on compare ce mois-ci par rapport au mois d'avant, et ainsi de suite. Ok, est-ce qu'on peut rajouter une période qui serait l'année ? L'année ce serait l'année 2026, *Year to Date*, tu as compris.

**Développeur :** Ah oui... oui oui... ça oui, c'est sûr que je peux le faire.

**Si Samir :** Ok...

**Développeur :** Donc ici nous avons « chaque dépense générale porte sa propre clé écrite », ça veut dire en toutes lettres. Plus de clé unique décidée une fois pour toutes. Ça veut dire qu'ici, excuse-moi...

**Si Samir :** Répète ça...

**Développeur :** Bien, juste une minute... on a dit ici que chaque dépense générale, comment comment ici... par exemple dans les frais généraux nous avons le gardiennage. Le gardiennage a sa propre clé : « recette ». Attends, je vais t'expliquer ça, juste une minute, parce qu'en fait, tu te souviens quand tu m'as dit... du cas par cas ?

**Si Samir :** Oui, il y a des choses qu'on divise en fonction de la manière de faire pour chacun.

**Développeur :** Ah, nous, en fait, ce que j'ai fait c'est que... j'ai créé une clé que j'ai nommée « recette », et une clé que j'ai nommée « dépense ». Et... et après, il y a un autre écran où... tu dois choisir ce qui relève de la recette et ce qui relève de la dépense. Tu as compris ? Donc... euh... c'est ça en fait.

**Si Samir :** Donc ici tu as les frais généraux par exemple, ok... tu vas y trouver les détails des frais, c'est bien ça ?

**Développeur :** Exact.

**Si Samir :** Euh... donc par exemple... le gardiennage par exemple, entre parenthèses 90%, c'est ça ?

**Développeur :** Exact. Sa clé c'est « recette ».

**Si Samir :** Pourquoi « recette » ? Je ne comprends pas « recette » par rapport à « dépense ».

**Développeur :** J'y arrive, j'y arrive, ça sera expliqué ici.

**Si Samir :** Ok bien bien... bien d'accord. Laisse ça de côté et on y reviendra... bien, revenons au reste.

**Développeur :** Donc chaque élément... on a dit qu'on a, comme je te l'ai dit, j'ai fait les clés par dépense et recette et tout ça. Et ensuite quoi... nous avons des frais qui ne sont pas... c'est-à-dire que dans la règle métier, ils ne sont pas déduits du... ils ne sont pas retirés du coût du lait. Attends, je t'explique... ah en fait voilà, c'est fait pour tout, bien attends juste...

**Si Samir :** Ça, ce serait bien dans cette page en fait d'avoir... je reviens vers toi, bien... ça, maintenant tu l'as... c'est le rapport de performance, ok, charge et coût du lait. C'est bien ça ou pas ?

**Développeur :** Oui...

**Si Samir :** Donc ça, c'est ce que tu as... dans le calcul du coût, c'est ça ?

**Développeur :** Euh... oui.

**Si Samir :** Bien... bien c'est bon. Ok. Après on fera la même chose mais ça sera... pour les recettes comme ça, je pense.

**Développeur :** Pas vraiment... j'y arrive, j'y arrive. Attends. Bien... chaque charge est rangée dans son atelier... comme tu l'as vu ici, c'est-à-dire que chaque charge... est dans son atelier. C'est clair ? Euh... et comme je te l'ai dit, on a une clé par dépense... dans les frais généraux on a... soit clé recette soit clé dépense... comme tu me l'avais dit lors de la réunion à l'époque. Et après je vais te montrer l'écran où, c'est-à-dire où cette clé est arbitrée. Tu me comprends ?

**Si Samir :** Bien, comme ça... je comprends, mais je veux voir les clés, montre-nous les clés. Comme ça, ça nous permet de « régler ça » une bonne fois pour toutes ?

**Développeur :** Bien, juste une minute... euh... ah voilà l'écran d'arbitrage. En fait, il y a deux façons dont on peut faire l'arbitrage. Soit on peut le faire comme ça... on fait l'arbitrage des frais généraux de juin 2026, où ici on peut mettre dans la « clé retenue »... tu choisis, par exemple pour le gardiennage tu choisis ici... est-ce que c'est sur la recette ou sur la dépense. Recette... à 90% et dépense 61,98%. C'est clair ? Et ici on voit son statut, si elle est arbitrée ou pas de votre part.

Ou bien... c'est-à-dire encore plus simple... ce qui est... comme ça : tu as... c'est-à-dire sur la facture d'achat, tu as... le comptage des charges... voici le montant, voici le centre de coût qui te dit quel est l'atelier... et tu choisis entre dépense et recette.

**Si Samir :** Je ne comprends pas ce que veut dire « clé de répartition », soit je le répartis par rapport aux dépenses, soit par rapport aux recettes, c'est ça ?

**Développeur :** C'est exactement ça, et parce qu'il y a les deux proratas... l'un à 90% et l'autre à 61,98%.

**Si Samir :** Par exemple disons, ok... nous, on n'a pas besoin d'avoir... une fois... Ce n'est pas uniquement comme ça. Tu vois ce que je veux dire ? Tu te compliques la tâche, laisse ça à 2 pourcentages : pour telle charge... euh... en dessous, le total doit faire 100%. Tu comprends ce que je veux dire ? Par exemple... nous... euh... quand on vient entrer une charge, ok, *User Story* entrer une charge, ok... je vais ouvrir, par exemple, on va entrer le gardiennage, ok, disons par exemple le gardiennage, ok. Euh... je ne vais pas entrer... euh... bon... on va dire par exemple, le gardiennage, c'est un ouvrier, ok. Lui, on va dire, peu importe, c'est une charge quelconque qu'on appellera service X. Ok. Gardiennage, je vais entrer un gardien. J'ai un gardien qui travaille uniquement du côté du lait. Il garde l'étable des vaches, voilà. Celui-là ira à 100% à l'atelier lait. Ou bien l'atelier élevage, donc nous on va le mettre à 100%, bien qu'il surveille les vaches et les génisses par exemple, on va le mettre pour le lait, ok, on décide de le mettre pour le lait, par exemple.

Ensuite... j'ai un autre gardien qui surveille les moutons. Par exemple d'un autre côté, c'est vrai, c'est du gardiennage, c'est des frais généraux, mais celui-là sera uniquement pour l'atelier brebis. Et j'en ai un autre au sein de la... au sein de la ferme... tu comprends, dans la ferme... qui surveille... d'un côté il surveille le parc et de l'autre il surveille la... par exemple la fromagerie, ok. Donc je vais mettre 50% ici et 50% là, par exemple. Ok. Tu as compris...

Donc, et par exemple, ou bien disons que j'ai 3 choses : ça, ça et ça, tu comprends. Donc il faut avoir la flexibilité de pouvoir faire « ajouter un atelier », « ajouter un atelier ». À chaque fois tu mets un pourcentage, et il ne te laisse pas sauvegarder tant que le total n'est pas à 100%, et c'est tout. Tu comprends l'idée ? Comment tu vas le diviser... par exemple, je vais décider dans le futur que la facture d'électricité, en ce moment on la divise seulement sur le lait. Le jour où il y aura la fromagerie, à ce moment-là on fera 50/50 par exemple, ok. Sans trop se compliquer la tête, tu comprends. Si c'est quelque chose lié aux recettes, par exemple au revenu total, ok. On va vraiment, par exemple, dire que mon salaire va être divisé sur le revenu de chaque atelier. Je ne vais pas le faire mois par mois. Je le ferai au début de l'année par exemple, en décembre, le 31 décembre à la clôture des caisses. En janvier, j'aurai un prorata, ça sera 10%, 15%, 20%, 30%, ok, je ne sais pas, total 100%. Tu comprends. Mais on le fera une seule fois. Ensuite, à chaque fois qu'ils viennent, ils l'entrent... tu comprends. Mais ces cas partagés-là, il n'y en a pas tant que ça, tu comprends. Donc ne perds pas trop de temps dessus. Du moment qu'on peut ajouter autant d'ateliers qu'on veut pour faire un total de 100% et c'est tout. Tu as compris... et ainsi de suite. Que ce soit partagé par rapport aux dépenses ou autre... ne te tracasse pas pour ça, tu comprends. Ça sera toujours par rapport à ce que le comptable va entrer et c'est tout. Et on parle peut-être d'un grand maximum... de 5 à 10 factures, tu as compris, bravo.

**Développeur :** Bien... donc le deuxième... ça veut dire, bien c'est bon, j'ai noté tout ce que tu m'as dit sur le premier écran... ce que je vais faire c'est qu'aujourd'hui, je vais essayer de refaire, c'est-à-dire faire une autre maquette avec toutes les remarques que tu m'as faites. Et j'essaierai de revenir...

**Si Samir :** Remonte en haut, excuse-moi, retourne à la première, on va terminer toutes tes slides comme ça on en profite pour te donner un maximum d'informations.

**Développeur :** Oui... bien... c'est bon...

**Si Samir :** Votre décision de lundi n'est pas...

**Développeur :** Juste attends... ah oui... ici c'était avant le fait qu'on ait une clé unique... mais c'est bon, ça, tu l'as...

**Si Samir :** Tu m'as compris, tout ça c'est vu. Ok.

**Développeur :** Donc ici on passe au deuxième écran qui est pour le parc et les interventions. Ici j'ai corrigé les choses que tu m'as dit de rajouter.

**Si Samir :** Agrandis s'il te plaît.

**Développeur :** Ah oui... Comme ça, ça va ? Comme ça ça va ou j'agrandis ?

**Si Samir :** Agrandis un peu, ok agrandis... ah c'est mieux comme ça, c'est mieux comme ça. Ok.

**Développeur :** Bien, donc la même logique hein... quand on met une date, pour les périodes je choisis la période adéquate : jour, mois... semaine, jour, semaine, mois... annuelle, tu as compris. Ok, bien. Rapport des interventions. Ok. Ici on a l'état du parc matériel... il y a, comme on a convenu, 3 états : État prêt, en attente de maintenance, en panne. Très bien. Et il y a la dernière intervention quand est-ce qu'elle a eu lieu, la prochaine intervention... et combien d'heures l'équipement a tourné. Bien. Dans les interventions... pareil, à l'époque tu m'as dit d'ajouter le type et d'ajouter beaucoup de choses ici...

**Si Samir :** Oui, intervention atelier, salle, ok oui. Pièce, main d'œuvre, coût, très bien. C'est quoi ce « *number one* », « *number* », oui. Les deux qui sont à la fin là, c'est quoi ? Nombre d'intervenants et... ça, franchement je l'ai oublié, mais je peux te dire ce que c'est.

**Développeur :** Intervenant, bien ce n'est pas un problème, ce n'est pas grave. État de l'unité... Bien... dans les interventions, par défaut il te donne ce qui est prévu... tu comprends. C'est plutôt par date, tu comprends... c'est-à-dire... il divise les interventions : toutes celles effectuées, en bas l'historique... et les prochaines (*upcoming*), tu as compris.

**Si Samir :** Ah je t'ai compris. Parce que l'historique, ça veut dire les interventions... c'est-à-dire... déjà effectuées, comme ça il peut y retourner, les ouvrir, et refaire par exemple « dupliquer une intervention ». Mettons ça, comme on l'a vu, on peut dupliquer une intervention. Qu'est-ce que ça veut dire, il va dupliquer l'intervention ? Ça veut dire qu'il va refaire la vidange, on a refait une vidange une autre fois, et c'est tout, tu as compris. Donc, il peut mettre une nouvelle date, il peut changer la date, mais ce qui est déjà terminé, effectué, on n'y touche plus, tu as compris. Tu vois ce que je veux dire ?

**Développeur :** Oui c'est clair.

**Si Samir :** Parce que ça sera plus facile pour lui... au lieu d'entrer, de choisir à nouveau et de mettre la quantité d'huile... s'il le fait correctement une fois, en principe c'est bon. Ensuite, il peut vérifier, si tout est bon, c'est bon, il enregistre, tu comprends.

**Développeur :** Bien. D'accord.

**Si Samir :** Les actions sur une intervention déjà effectuée : soit tu l'enlèves complètement, tu peux la supprimer (*deleter*)... s'il y a un problème il peut la supprimer... il peut l'enlever. Soit une nouvelle intervention, ou bien... planifier une intervention, tu comprends. Ou planifier, c'est une nouvelle intervention sauf que la date est dans le futur et c'est tout. Elle reste ouverte... il met « planifier »...

**Développeur :** Planifier... qu'est-ce que ça veut dire un « rapprochement » ?

**Si Samir :** Un rapprochement ça veut dire... il y a une différence entre ce qu'on a dépensé et ce dont on... on n'a pas exactement les traces, ou quoi que ce soit. C'est ça.

**Développeur :** J'ai compris. Ok. Bien, bien. Oui, des interventions saisies et l'... état... Ok, d'accord.

**Si Samir :** Tu as compris la logique des interventions, quand tu viens faire une intervention, pense au fait que lui, premièrement ce n'est pas un informaticien, donc ce n'est pas son travail [segment abîmé] je n'ai rien oublié tu comprends ? Donc dans quelques heures, tout sera clair.

**Si Samir :** Ok, très bien. Merci. Merci à toi. Au revoir, bon courage. Au revoir.
