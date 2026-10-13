import ImageIO
import UIKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        let w = UIWindow(frame: UIScreen.main.bounds)
        w.rootViewController = EcranController()
        w.makeKeyAndVisible()
        window = w
        application.isIdleTimerDisabled = true // l'ecran ne se met pas en veille
        return true
    }
}

final class EcranController: UIViewController {
    private let lien = Lien()
    private let surface = Surface()
    private let message = UILabel()

    private let fileDecodage = DispatchQueue(label: "decodage", qos: .userInteractive)
    private let verrou = NSLock()
    private var prochaine: Data?
    private var decodageEnCours = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        surface.frame = view.bounds
        surface.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        surface.lien = lien
        view.addSubview(surface)

        message.text = "En attente du PC…\nBranche l'iPad en USB et lance serveur.py sur le PC."
        message.numberOfLines = 0
        message.textAlignment = .center
        message.textColor = .lightGray
        message.font = .systemFont(ofSize: 22, weight: .medium)
        message.frame = view.bounds
        message.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        message.isUserInteractionEnabled = false
        view.addSubview(message)

        lien.surImage = { [weak self] d in self?.recevoirImage(d) }
        lien.surEtat = { [weak self] connecte in self?.message.isHidden = connecte }
        lien.demarrer()
    }

    /// Ne decode que l'image la plus recente : si le PC va plus vite que l'iPad, on saute des images
    /// au lieu d'accumuler du retard.
    private func recevoirImage(_ d: Data) {
        verrou.lock()
        prochaine = d
        let lancer = !decodageEnCours
        if lancer { decodageEnCours = true }
        verrou.unlock()
        if lancer {
            fileDecodage.async { [weak self] in self?.boucleDecodage() }
        }
    }

    private func boucleDecodage() {
        while true {
            verrou.lock()
            guard let d = prochaine else {
                decodageEnCours = false
                verrou.unlock()
                return
            }
            prochaine = nil
            verrou.unlock()

            let options = [kCGImageSourceShouldCacheImmediately: true] as CFDictionary
            guard let source = CGImageSourceCreateWithData(d as CFData, nil),
                  let image = CGImageSourceCreateImageAtIndex(source, 0, options) else { continue }
            DispatchQueue.main.async { [weak self] in self?.surface.afficher(image) }
        }
    }

    override var prefersStatusBarHidden: Bool { true }
    override var prefersHomeIndicatorAutoHidden: Bool { true }
    override var preferredScreenEdgesDeferringSystemGestures: UIRectEdge { .all }
}
