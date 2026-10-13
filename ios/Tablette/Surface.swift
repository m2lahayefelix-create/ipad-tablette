import UIKit

/// Affiche l'ecran du PC et renvoie chaque trait du stylet.
final class Surface: UIView {
    var lien: Lien?

    private let calque = CALayer()
    private var tailleImage = CGSize(width: 16, height: 9)
    private var toucheActive: UITouch?
    private var pencilVu = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        isMultipleTouchEnabled = true
        backgroundColor = .black
        calque.contentsGravity = .resizeAspect
        layer.addSublayer(calque)
    }

    required init?(coder: NSCoder) { fatalError("non utilise") }

    override func layoutSubviews() {
        super.layoutSubviews()
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        calque.frame = bounds
        CATransaction.commit()
    }

    func afficher(_ image: CGImage) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        calque.contents = image
        CATransaction.commit()
        tailleImage = CGSize(width: image.width, height: image.height)
    }

    /// Zone occupee par l'image (meme calcul que .resizeAspect).
    private func zoneImage() -> CGRect {
        let echelle = min(bounds.width / tailleImage.width, bounds.height / tailleImage.height)
        let l = tailleImage.width * echelle
        let h = tailleImage.height * echelle
        return CGRect(x: (bounds.width - l) / 2, y: (bounds.height - h) / 2, width: l, height: h)
    }

    // MARK: - Touches

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        for t in touches {
            if t.type == .pencil {
                pencilVu = true
                // le stylet prend la main sur un doigt (paume posee)
                if let a = toucheActive, a.type != .pencil {
                    envoyer(a, phase: 4)
                    toucheActive = nil
                }
            }
            if toucheActive != nil { continue }
            if t.type != .pencil && pencilVu { continue } // rejet de la paume
            toucheActive = t
            envoyer(t, phase: 1)
        }
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let a = toucheActive, touches.contains(a) else { return }
        let serie = event?.coalescedTouches(for: a) ?? [a]
        for t in serie {
            envoyer(t, phase: 2)
        }
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let a = toucheActive, touches.contains(a) else { return }
        envoyer(a, phase: 3)
        toucheActive = nil
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let a = toucheActive, touches.contains(a) else { return }
        envoyer(a, phase: 4)
        toucheActive = nil
    }

    private func envoyer(_ t: UITouch, phase: UInt8) {
        let zone = zoneImage()
        let p = t.preciseLocation(in: self)
        let x = Float((p.x - zone.minX) / zone.width)
        let y = Float((p.y - zone.minY) / zone.height)
        var pression: Float = -1
        var altitude = Float.pi / 2
        var azimut: Float = 0
        if t.type == .pencil {
            if t.maximumPossibleForce > 0 {
                pression = Float(t.force / t.maximumPossibleForce)
            }
            altitude = Float(t.altitudeAngle)
            azimut = Float(t.azimuthAngle(in: self))
        }
        var d = Data([phase, t.type == .pencil ? 1 : 0])
        for v in [x, y, pression, altitude, azimut] {
            var be = v.bitPattern.bigEndian
            d.append(withUnsafeBytes(of: &be) { Data($0) })
        }
        lien?.envoyer(type: Lien.typeTrait, d)
    }
}
