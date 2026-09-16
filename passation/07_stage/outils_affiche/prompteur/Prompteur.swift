// Prompteur invisible pour la soutenance en ligne.
// Fenêtre flottante, toujours au premier plan, exclue de la capture d'écran et
// du partage d'écran (NSWindow.sharingType = .none). Lit prompteur.json.
//
// Tout le texte est dans une seule page qui défile (molette, trackpad, ↑ ↓,
// espace = page). Le bandeau du haut suit le bloc en cours de lecture.
// Clavier : ↓ ↑ = défiler · espace / page = une page · → ← = sauter au bloc suivant/précédent
//           + / - = taille du texte · T = chrono marche/arrêt · R = remise à zéro
//           O = opacité · H = masquer/afficher · ⌘Q = quitter
// Lancement : open Prompteur.app   (ou  Prompteur.app/Contents/MacOS/Prompteur --visible  pour
// une répétition où la fenêtre reste capturable, ex. pour vérifier son rendu).
import AppKit
import CoreGraphics

struct Bloc: Decodable {
    let partie: String
    let zone: String
    let bloc: String
    let minutes: Double
    let debut: Double
    let dire: String
    let montrer: String
    let question: String
}

// NSPanel non activant : reste visible par-dessus les apps en plein écran (Zoom, Chrome, Keynote…)
// et cliquer dessus ne fait pas quitter l'espace plein écran de l'autre app.
final class PrompteurWindow: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
    var onKey: ((NSEvent) -> Bool)?
    override func keyDown(with event: NSEvent) {
        if onKey?(event) == true { return }
        super.keyDown(with: event)
    }
}

final class App: NSObject, NSApplicationDelegate {
    var window: PrompteurWindow!
    var blocs: [Bloc] = []
    var index = 0 { didSet { if index != oldValue { updateHeader() } } }
    var blocStarts: [Int] = []   // position (caractères) du début de chaque bloc dans le texte
    var fontSize: CGFloat = 20
    let textView = NSTextView()
    let scroll = NSScrollView()
    let header = NSTextField(labelWithString: "")
    let footer = NSTextField(labelWithString: "")
    let chrono = NSTextField(labelWithString: "00:00")
    var timer: Timer?
    var started: Date?
    var accumulated: TimeInterval = 0
    var opacities: [CGFloat] = [0.92, 0.75, 0.55]
    var opacityIdx = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        loadBlocs()
        buildMenu()
        buildWindow()
        render()
        updateHeader()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); return false
    }

    // MARK: données
    func loadBlocs() {
        let args = CommandLine.arguments.filter { !$0.hasPrefix("--") }
        var url: URL?
        if args.count > 1 { url = URL(fileURLWithPath: args[1]) }
        if url == nil { url = Bundle.main.url(forResource: "prompteur", withExtension: "json") }
        if url == nil {
            let exe = URL(fileURLWithPath: args[0]).deletingLastPathComponent()
            url = exe.appendingPathComponent("prompteur.json")
        }
        guard let u = url, let data = try? Data(contentsOf: u),
              let parsed = try? JSONDecoder().decode([Bloc].self, from: data), !parsed.isEmpty else {
            blocs = [Bloc(partie: "Erreur", zone: "", bloc: "prompteur.json introuvable",
                          minutes: 0, debut: 0,
                          dire: "Lance : python3 outils_affiche/build_guide_photos.py puis relance le prompteur, ou passe le chemin du JSON en argument.",
                          montrer: "", question: "")]
            return
        }
        blocs = parsed
    }

    // MARK: fenêtre
    func buildWindow() {
        let screen = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1200, height: 800)
        let w: CGFloat = 520, h: CGFloat = 620
        let rect = NSRect(x: screen.maxX - w - 20, y: screen.maxY - h - 20, width: w, height: h)
        window = PrompteurWindow(contentRect: rect,
                                 styleMask: [.titled, .closable, .resizable, .fullSizeContentView, .nonactivatingPanel],
                                 backing: .buffered, defer: false)
        window.title = "Prompteur"
        window.titlebarAppearsTransparent = true
        window.titleVisibility = .hidden
        window.isMovableByWindowBackground = true
        // niveau du voile d'écran (verrouillage/mot de passe), le plus haut que l'OS
        // laisse utiliser : assistiveTechHigh (1500) s'est révélé encore trop bas face à
        // la fenêtre de présentation Keynote Play, qui dépasse ce niveau.
        let maxLevel = Int(CGWindowLevelForKey(.maximumWindow))
        window.level = NSWindow.Level(rawValue: min(Int(CGShieldingWindowLevel()) + 1, maxLevel))
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        window.hidesOnDeactivate = false
        window.isFloatingPanel = true
        window.becomesKeyOnlyIfNeeded = false
        // invisible à la capture d'écran et au partage, sauf lancé avec --visible (répétition)
        window.sharingType = CommandLine.arguments.contains("--visible") ? .readOnly : .none
        window.isOpaque = false
        window.backgroundColor = NSColor(calibratedWhite: 0.08, alpha: 1)
        window.alphaValue = opacities[opacityIdx]
        window.appearance = NSAppearance(named: .darkAqua)
        window.minSize = NSSize(width: 320, height: 240)
        window.onKey = { [weak self] e in self?.handleKey(e) ?? false }

        let content = NSView()
        window.contentView = content

        header.font = NSFont.systemFont(ofSize: 13, weight: .semibold)
        header.textColor = NSColor(calibratedRed: 0.55, green: 0.65, blue: 1, alpha: 1)
        header.lineBreakMode = .byTruncatingTail
        header.maximumNumberOfLines = 2
        header.translatesAutoresizingMaskIntoConstraints = false

        textView.isEditable = false
        textView.isSelectable = false
        textView.drawsBackground = false
        textView.textContainerInset = NSSize(width: 6, height: 8)
        textView.textContainer?.lineFragmentPadding = 10
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.autoresizingMask = [.width]
        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true
        textView.textContainer?.containerSize = NSSize(width: w - 16, height: CGFloat.greatestFiniteMagnitude)
        textView.frame = NSRect(x: 0, y: 0, width: w - 16, height: 100)
        scroll.documentView = textView
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.scrollerStyle = .overlay
        scroll.contentView.postsBoundsChangedNotifications = true
        NotificationCenter.default.addObserver(self, selector: #selector(scrolled), name: NSView.boundsDidChangeNotification, object: scroll.contentView)

        chrono.font = NSFont.monospacedDigitSystemFont(ofSize: 22, weight: .bold)
        chrono.textColor = .white
        chrono.translatesAutoresizingMaskIntoConstraints = false

        footer.font = NSFont.systemFont(ofSize: 12)
        footer.textColor = NSColor(calibratedWhite: 0.7, alpha: 1)
        footer.lineBreakMode = .byTruncatingTail
        footer.translatesAutoresizingMaskIntoConstraints = false
        footer.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        header.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        let prev = NSButton(title: "◀", target: self, action: #selector(prevBloc))
        let next = NSButton(title: "▶", target: self, action: #selector(nextBloc))
        let play = NSButton(title: "⏱", target: self, action: #selector(toggleTimer))
        for b in [prev, next, play] {
            b.bezelStyle = .rounded
            b.translatesAutoresizingMaskIntoConstraints = false
            content.addSubview(b)
        }
        content.addSubview(header)
        content.addSubview(scroll)
        content.addSubview(chrono)
        content.addSubview(footer)

        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: content.topAnchor, constant: 30),
            header.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 14),
            header.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -14),

            scroll.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 6),
            scroll.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 8),
            scroll.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -8),
            scroll.bottomAnchor.constraint(equalTo: chrono.topAnchor, constant: -8),

            chrono.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 14),
            chrono.bottomAnchor.constraint(equalTo: footer.topAnchor, constant: -2),

            play.centerYAnchor.constraint(equalTo: chrono.centerYAnchor),
            play.leadingAnchor.constraint(equalTo: chrono.trailingAnchor, constant: 10),
            prev.centerYAnchor.constraint(equalTo: chrono.centerYAnchor),
            next.centerYAnchor.constraint(equalTo: chrono.centerYAnchor),
            next.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -14),
            prev.trailingAnchor.constraint(equalTo: next.leadingAnchor, constant: -6),

            footer.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 14),
            footer.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -14),
            footer.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -10),
        ])
        window.makeKeyAndOrderFront(nil)
    }

    func buildMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Masquer le prompteur (H)", action: #selector(toggleHidden), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Quitter", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)
        NSApp.mainMenu = main
    }

    // MARK: rendu — tout le texte dans une seule page
    func render() {
        guard !blocs.isEmpty else { return }
        let para = NSMutableParagraphStyle()
        para.lineSpacing = fontSize * 0.28
        para.paragraphSpacing = fontSize * 0.6
        let titrePara = NSMutableParagraphStyle()
        titrePara.paragraphSpacingBefore = fontSize * 1.4
        titrePara.paragraphSpacing = fontSize * 0.4
        let partiePara = NSMutableParagraphStyle()
        partiePara.paragraphSpacingBefore = fontSize * 2.2
        partiePara.paragraphSpacing = fontSize * 0.2
        let body: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize, weight: .regular),
            .foregroundColor: NSColor.white, .paragraphStyle: para]
        let muted: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize * 0.75),
            .foregroundColor: NSColor(calibratedWhite: 0.72, alpha: 1), .paragraphStyle: para]
        let label: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize * 0.75, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0.95, green: 0.8, blue: 0.35, alpha: 1), .paragraphStyle: para]
        let partieAttr: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize * 0.7, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0.55, green: 0.65, blue: 1, alpha: 1), .paragraphStyle: partiePara]
        let titreAttr: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize * 0.95, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0.55, green: 0.65, blue: 1, alpha: 1), .paragraphStyle: titrePara]

        let s = NSMutableAttributedString()
        blocStarts = []
        var partieCourante = ""
        for b in blocs {
            blocStarts.append(s.length)
            if b.partie != partieCourante {
                partieCourante = b.partie
                s.append(NSAttributedString(string: "━━  \(b.partie.uppercased())\n", attributes: partieAttr))
            }
            s.append(NSAttributedString(string: "\(b.bloc)   ·   \(fmt(b.debut)) → \(fmt(b.debut + b.minutes))\n", attributes: titreAttr))
            s.append(NSAttributedString(string: b.dire + "\n", attributes: body))
            if !b.montrer.isEmpty {
                s.append(NSAttributedString(string: "Montrer : ", attributes: label))
                s.append(NSAttributedString(string: b.montrer + "\n", attributes: muted))
            }
            if !b.question.isEmpty {
                s.append(NSAttributedString(string: "Si on demande : ", attributes: label))
                s.append(NSAttributedString(string: b.question + "\n", attributes: muted))
            }
        }
        s.append(NSAttributedString(string: "\n\n\n— fin —\n\n\n\n\n\n\n\n\n\n\n\n", attributes: muted))
        // garder la position de lecture (en proportion) quand la taille du texte change
        let clip = scroll.contentView
        let ratio = textView.frame.height > 0 ? clip.bounds.origin.y / textView.frame.height : 0
        textView.textStorage?.setAttributedString(s)
        textView.layoutManager?.ensureLayout(for: textView.textContainer!)
        clip.scroll(to: NSPoint(x: 0, y: max(0, ratio * textView.frame.height)))
        scroll.reflectScrolledClipView(clip)
        footer.stringValue = "\(blocs.count) blocs  ·  ↓ ↑ défiler  ·  espace page  ·  → ← bloc  ·  + / - texte  ·  T chrono  ·  R zéro  ·  O opacité  ·  H masquer"
        scrolled()
    }

    /// Bloc en cours de lecture = dernier bloc dont le début est au-dessus du tiers haut de la fenêtre.
    @objc func scrolled() {
        guard let lm = textView.layoutManager, let tc = textView.textContainer, !blocStarts.isEmpty else { return }
        let top = scroll.contentView.bounds.origin.y + scroll.contentView.bounds.height * 0.3
        var current = 0
        for (i, start) in blocStarts.enumerated() {
            let g = lm.glyphIndexForCharacter(at: min(start, max(0, (textView.string as NSString).length - 1)))
            let y = lm.lineFragmentRect(forGlyphAt: g, effectiveRange: nil).origin.y + textView.textContainerInset.height
            if y <= top { current = i } else { break }
        }
        _ = tc
        index = current
    }

    func updateHeader() {
        let b = blocs[index]
        header.stringValue = "\(b.partie)  ·  \(b.bloc)\nPrévu : \(fmt(b.debut)) → \(fmt(b.debut + b.minutes))  (\(trim(b.minutes)) min)"
        updateChrono()
    }

    func scrollToBloc(_ i: Int) {
        guard let lm = textView.layoutManager, i >= 0, i < blocStarts.count else { return }
        let g = lm.glyphIndexForCharacter(at: blocStarts[i])
        let y = lm.lineFragmentRect(forGlyphAt: g, effectiveRange: nil).origin.y + textView.textContainerInset.height
        let clip = scroll.contentView
        clip.scroll(to: NSPoint(x: 0, y: max(0, y - 4)))
        scroll.reflectScrolledClipView(clip)
    }

    func scrollBy(_ dy: CGFloat) {
        let clip = scroll.contentView
        let maxY = max(0, textView.frame.height - clip.bounds.height)
        clip.scroll(to: NSPoint(x: 0, y: min(maxY, max(0, clip.bounds.origin.y + dy))))
        scroll.reflectScrolledClipView(clip)
    }

    func fmt(_ minutes: Double) -> String {
        let total = Int((minutes * 60).rounded())
        return String(format: "%d:%02d", total / 60, total % 60)
    }
    func trim(_ v: Double) -> String { v == v.rounded() ? String(Int(v)) : String(v) }

    // MARK: chrono
    var elapsed: TimeInterval { accumulated + (started.map { Date().timeIntervalSince($0) } ?? 0) }

    @objc func toggleTimer() {
        if let s = started {
            accumulated += Date().timeIntervalSince(s)
            started = nil
            timer?.invalidate(); timer = nil
        } else {
            started = Date()
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in self?.updateChrono() }
        }
        updateChrono()
    }

    func resetTimer() {
        timer?.invalidate(); timer = nil
        started = nil; accumulated = 0
        updateChrono()
    }

    func updateChrono() {
        let e = Int(elapsed)
        let b = blocs[index]
        let planned = b.debut * 60
        let delta = Double(e) - planned
        let sign = delta >= 0 ? "+" : "−"
        let d = Int(abs(delta))
        chrono.stringValue = String(format: "%02d:%02d  %@%d:%02d", e / 60, e % 60, sign, d / 60, d % 60)
        // vert : en avance ou dans le bloc ; orange : > 1 min de retard ; rouge : > 3 min
        if delta > 180 { chrono.textColor = NSColor(calibratedRed: 1, green: 0.4, blue: 0.4, alpha: 1) }
        else if delta > 60 { chrono.textColor = NSColor(calibratedRed: 1, green: 0.75, blue: 0.3, alpha: 1) }
        else { chrono.textColor = NSColor(calibratedRed: 0.55, green: 0.9, blue: 0.6, alpha: 1) }
        if started == nil { chrono.textColor = chrono.textColor?.withAlphaComponent(0.6) }
    }

    // MARK: navigation
    @objc func nextBloc() { scrollToBloc(min(blocs.count - 1, index + 1)) }
    @objc func prevBloc() { scrollToBloc(max(0, index - 1)) }
    @objc func toggleHidden() {
        if window.isVisible { window.orderOut(nil) } else { window.makeKeyAndOrderFront(nil) }
    }

    func handleKey(_ e: NSEvent) -> Bool {
        if e.modifierFlags.contains(.command) {
            if e.charactersIgnoringModifiers?.lowercased() == "q" { NSApp.terminate(nil); return true }
            if e.charactersIgnoringModifiers?.lowercased() == "w" { toggleHidden(); return true }
            return false
        }
        let page = scroll.contentView.bounds.height * 0.85
        switch e.keyCode {
        case 125: scrollBy(fontSize * 3); return true                 // ↓
        case 126: scrollBy(-fontSize * 3); return true                // ↑
        case 49, 121: scrollBy(e.modifierFlags.contains(.shift) ? -page : page); return true  // espace, page down
        case 116: scrollBy(-page); return true                        // page up
        case 124, 36: nextBloc(); return true                         // →, entrée : bloc suivant
        case 123: prevBloc(); return true                             // ← : bloc précédent
        case 115: scrollToBloc(0); return true                        // début
        case 53: toggleHidden(); return true                          // échap : masquer
        default: break
        }
        switch e.charactersIgnoringModifiers?.lowercased() {
        case "+", "=": fontSize = min(48, fontSize + 2); render(); return true
        case "-", "_": fontSize = max(12, fontSize - 2); render(); return true
        case "t": toggleTimer(); return true
        case "r": resetTimer(); return true
        case "o": opacityIdx = (opacityIdx + 1) % opacities.count; window.alphaValue = opacities[opacityIdx]; return true
        case "h": toggleHidden(); return true
        case "n", "j": nextBloc(); return true
        case "p", "k": prevBloc(); return true
        default: return false
        }
    }
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate = App()
app.delegate = delegate
app.run()
