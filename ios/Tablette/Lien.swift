import Foundation
import Network

/// Ecoute sur le port 2345 de l'iPad. Le PC s'y connecte par le cable USB (usbmux).
/// Messages : [type 1 octet][longueur 4 octets big-endian][donnees]
final class Lien {
    static let port: UInt16 = 2345
    static let typeImage: UInt8 = 0x01
    static let typeTrait: UInt8 = 0x10

    var surImage: ((Data) -> Void)?
    var surEtat: ((Bool) -> Void)?

    private var ecouteur: NWListener?
    private var connexion: NWConnection?
    private let file = DispatchQueue(label: "lien", qos: .userInteractive)
    private var tampon = Data()

    func demarrer() {
        file.async { self.ouvrirEcoute() }
    }

    private func ouvrirEcoute() {
        let tcp = NWProtocolTCP.Options()
        tcp.noDelay = true
        let parametres = NWParameters(tls: nil, tcp: tcp)
        parametres.allowLocalEndpointReuse = true
        do {
            let e = try NWListener(using: parametres, on: NWEndpoint.Port(rawValue: Lien.port)!)
            e.newConnectionHandler = { [weak self] c in self?.accepter(c) }
            e.stateUpdateHandler = { [weak self] etat in
                if case .failed = etat { self?.relancerEcoute() }
            }
            e.start(queue: file)
            ecouteur = e
        } catch {
            relancerEcoute()
        }
    }

    private func relancerEcoute() {
        ecouteur?.cancel()
        ecouteur = nil
        file.asyncAfter(deadline: .now() + 1) { [weak self] in self?.ouvrirEcoute() }
    }

    private func accepter(_ c: NWConnection) {
        connexion?.cancel()
        connexion = c
        tampon = Data()
        c.stateUpdateHandler = { [weak self, weak c] etat in
            guard let self = self, let c = c else { return }
            switch etat {
            case .ready:
                DispatchQueue.main.async { self.surEtat?(true) }
            case .failed, .cancelled:
                if self.connexion === c {
                    self.connexion = nil
                    DispatchQueue.main.async { self.surEtat?(false) }
                }
            default:
                break
            }
        }
        c.start(queue: file)
        recevoir(c)
    }

    private func recevoir(_ c: NWConnection) {
        c.receive(minimumIncompleteLength: 1, maximumLength: 1 << 20) { [weak self] donnees, _, fini, erreur in
            guard let self = self else { return }
            if let donnees = donnees, !donnees.isEmpty {
                self.tampon.append(donnees)
                self.decouper()
            }
            if fini || erreur != nil {
                c.cancel()
                return
            }
            self.recevoir(c)
        }
    }

    private func decouper() {
        while tampon.count >= 5 {
            let entete = [UInt8](tampon.prefix(5))
            let type = entete[0]
            let longueur = Int(entete[1]) << 24 | Int(entete[2]) << 16 | Int(entete[3]) << 8 | Int(entete[4])
            guard tampon.count >= 5 + longueur else { return }
            let debut = tampon.startIndex + 5
            let message = tampon.subdata(in: debut ..< debut + longueur)
            tampon = Data(tampon[(debut + longueur)...])
            if type == Lien.typeImage {
                surImage?(message)
            }
        }
    }

    func envoyer(type: UInt8, _ contenu: Data) {
        file.async { [weak self] in
            guard let c = self?.connexion else { return }
            var paquet = Data([type])
            var longueur = UInt32(contenu.count).bigEndian
            paquet.append(withUnsafeBytes(of: &longueur) { Data($0) })
            paquet.append(contenu)
            c.send(content: paquet, completion: .idempotent)
        }
    }
}
