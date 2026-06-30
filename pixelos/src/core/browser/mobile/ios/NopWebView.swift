import UIKit
import WebKit

/// NOP Browser — iOS WKWebView with Web3 resolution, ad blocking, and wallet bridge.
///
/// Communication with the NOP Python bridge happens via local HTTP on port 9876.
/// Build: Open in Xcode → Run on device/simulator.
///
/// Requirements: iOS 15.0+, Xcode 14+

@main
class NopAppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        window = UIWindow(frame: UIScreen.main.bounds)
        window?.rootViewController = NopViewController()
        window?.makeKeyAndVisible()
        return true
    }
}

class NopViewController: UIViewController, WKNavigationDelegate, WKUIDelegate {

    // MARK: - Properties
    private var webView: WKWebView!
    private var urlBar: UITextField!
    private var btnBack: UIButton!
    private var btnForward: UIButton!
    private var btnRefresh: UIButton!
    private var btnMenu: UIButton!
    private var badgeWeb3: UILabel!
    private var progressBar: UIProgressView!
    private var bottomToolbar: UIToolbar!

    private let nopBridge = "http://127.0.0.1:9876"
    private var currentUrl = ""
    private var bookmarks: [[String: String]] = []
    private var history: [[String: String]] = []
    private var observations: [NSKeyValueObservation] = []

    // MARK: - Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        setupUI()
        setupWebView()
        loadUrl("https://duckduckgo.com")
    }

    // MARK: - UI Setup
    private func setupUI() {
        view.backgroundColor = UIColor(red: 0.12, green: 0.12, blue: 0.18, alpha: 1)

        // URL Bar
        urlBar = UITextField()
        urlBar.translatesAutoresizingMaskIntoConstraints = false
        urlBar.placeholder = "URL ou recherche..."
        urlBar.borderStyle = .roundedRect
        urlBar.backgroundColor = UIColor(red: 0.18, green: 0.18, blue: 0.27, alpha: 1)
        urlBar.textColor = UIColor(red: 0.80, green: 0.84, blue: 0.96, alpha: 1)
        urlBar.keyboardType = .webSearch
        urlBar.returnKeyType = .go
        urlBar.clearButtonMode = .whileEditing
        urlBar.layer.cornerRadius = 16
        urlBar.clipsToBounds = true
        urlBar.delegate = self
        view.addSubview(urlBar)

        // Web3 Badge
        badgeWeb3 = UILabel()
        badgeWeb3.translatesAutoresizingMaskIntoConstraints = false
        badgeWeb3.text = "🌐"
        badgeWeb3.font = UIFont.systemFont(ofSize: 11, weight: .bold)
        badgeWeb3.textColor = UIColor(red: 0.80, green: 0.84, blue: 0.96, alpha: 1)
        badgeWeb3.backgroundColor = UIColor(red: 0.06, green: 0.20, blue: 0.38, alpha: 1)
        badgeWeb3.textAlignment = .center
        badgeWeb3.layer.cornerRadius = 12
        badgeWeb3.clipsToBounds = true
        view.addSubview(badgeWeb3)

        // Progress bar
        progressBar = UIProgressView(progressViewStyle: .bar)
        progressBar.translatesAutoresizingMaskIntoConstraints = false
        progressBar.trackTintColor = UIColor(red: 0.18, green: 0.18, blue: 0.27, alpha: 1)
        progressBar.progressTintColor = UIColor(red: 0.91, green: 0.27, blue: 0.38, alpha: 1)
        view.addSubview(progressBar)

        // WebView
        let config = WKWebViewConfiguration()
        config.websiteDataStore = WKWebsiteDataStore.default()
        config.defaultWebpagePreferences.preferredContentMode = .mobile

        webView = WKWebView(frame: .zero, configuration: config)
        webView.translatesAutoresizingMaskIntoConstraints = false
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.backgroundColor = UIColor(red: 0.12, green: 0.12, blue: 0.18, alpha: 1)
        webView.allowsBackForwardNavigationGestures = true
        view.addSubview(webView)

        // Bottom toolbar
        bottomToolbar = UIToolbar()
        bottomToolbar.translatesAutoresizingMaskIntoConstraints = false
        bottomToolbar.barStyle = .black
        bottomToolbar.tintColor = UIColor(red: 0.80, green: 0.84, blue: 0.96, alpha: 1)

        btnBack = UIButton(type: .system)
        btnBack.setTitle("◀", for: .normal)
        btnBack.addTarget(self, action: #selector(goBack), for: .touchUpInside)

        btnForward = UIButton(type: .system)
        btnForward.setTitle("▶", for: .normal)
        btnForward.addTarget(self, action: #selector(goForward), for: .touchUpInside)

        btnRefresh = UIButton(type: .system)
        btnRefresh.setTitle("⟳", for: .normal)
        btnRefresh.addTarget(self, action: #selector(refresh), for: .touchUpInside)

        btnMenu = UIButton(type: .system)
        btnMenu.setTitle("⚙", for: .normal)
        btnMenu.addTarget(self, action: #selector(showMenu), for: .touchUpInside)

        let flexSpace = UIBarButtonItem(barButtonSystemItem: .flexibleSpace, target: nil, action: nil)
        let stack = UIStackView(arrangedSubviews: [btnBack, btnForward, btnRefresh, btnMenu])
        stack.axis = .horizontal
        stack.spacing = 40
        stack.distribution = .fillEqually
        let barItem = UIBarButtonItem(customView: stack)
        bottomToolbar.items = [flexSpace, barItem, flexSpace]

        view.addSubview(bottomToolbar)

        // Auto Layout
        let safe = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            urlBar.topAnchor.constraint(equalTo: safe.topAnchor, constant: 8),
            urlBar.leadingAnchor.constraint(equalTo: safe.leadingAnchor, constant: 8),
            urlBar.trailingAnchor.constraint(equalTo: badgeWeb3.leadingAnchor, constant: -8),
            urlBar.heightAnchor.constraint(equalToConstant: 40),

            badgeWeb3.centerYAnchor.constraint(equalTo: urlBar.centerYAnchor),
            badgeWeb3.trailingAnchor.constraint(equalTo: safe.trailingAnchor, constant: -8),
            badgeWeb3.widthAnchor.constraint(greaterThanOrEqualToConstant: 50),
            badgeWeb3.heightAnchor.constraint(equalToConstant: 28),

            progressBar.topAnchor.constraint(equalTo: urlBar.bottomAnchor, constant: 4),
            progressBar.leadingAnchor.constraint(equalTo: safe.leadingAnchor),
            progressBar.trailingAnchor.constraint(equalTo: safe.trailingAnchor),
            progressBar.heightAnchor.constraint(equalToConstant: 2),

            webView.topAnchor.constraint(equalTo: progressBar.bottomAnchor, constant: 4),
            webView.leadingAnchor.constraint(equalTo: safe.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: safe.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: bottomToolbar.topAnchor),

            bottomToolbar.leadingAnchor.constraint(equalTo: safe.leadingAnchor),
            bottomToolbar.trailingAnchor.constraint(equalTo: safe.trailingAnchor),
            bottomToolbar.bottomAnchor.constraint(equalTo: safe.bottomAnchor),
            bottomToolbar.heightAnchor.constraint(equalToConstant: 44),
        ])
    }

    // MARK: - WebView Setup
    private func setupWebView() {
        // Ad blocking: WKContentRuleList
        let adBlockJSON = """
        [{
            "trigger": {
                "url-filter": ".*",
                "resource-type": ["image", "script", "xmlhttprequest", "fetch"],
                "if-domain": ["*doubleclick.net", "*googlesyndication.com", "*googleadservices.com",
                              "*google-analytics.com", "*googletagmanager.com", "*facebook.com",
                              "*amazon-adsystem.com", "*adsrvr.org", "*pubmatic.com", "*criteo.com",
                              "*outbrain.com", "*taboola.com", "*scorecardresearch.com"]
            },
            "action": { "type": "block" }
        }]
        """

        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "NOPAdBlock",
            encodedContentRuleList: adBlockJSON
        ) { [weak self] ruleList, error in
            guard let self = self, let ruleList = ruleList else { return }
            let config = self.webView.configuration
            config.userContentController.add(ruleList)
        }
    }

    // MARK: - Navigation
    private func loadUrl(_ input: String) {
        var urlStr = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !urlStr.isEmpty else { return }

        // Web3 resolution
        if urlStr.contains(".eth") || urlStr.contains(".pixel") || urlStr.contains(".pxl") ||
           urlStr.contains(".ipfs") || urlStr.contains(".bit") || urlStr.contains(".crypto") {
            resolveWeb3(urlStr)
            return
        }

        if !urlStr.hasPrefix("http://") && !urlStr.hasPrefix("https://") {
            if urlStr.contains(".") {
                urlStr = "https://" + urlStr
            } else {
                let encoded = urlStr.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
                urlStr = "https://duckduckgo.com/?q=\(encoded)"
            }
        }

        guard let url = URL(string: urlStr) else { return }
        webView.load(URLRequest(url: url))
        urlBar.text = urlStr
        addHistory(urlStr)
    }

    private func resolveWeb3(_ input: String) {
        guard let encoded = input.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(nopBridge)/resolve?url=\(encoded)") else { return }

        URLSession.shared.dataTask(with: url) { [weak self] data, _, error in
            guard let self = self, let data = data,
                  let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let resolved = json["resolved_url"] as? String else { return }

            DispatchQueue.main.async {
                let web3Type = json["web3_type"] as? String ?? "standard"
                self.updateWeb3Badge(web3Type)
                guard let finalUrl = URL(string: resolved) else { return }
                self.webView.load(URLRequest(url: finalUrl))
                self.urlBar.text = resolved
                self.addHistory(resolved)
            }
        }.resume()
    }

    private func updateWeb3Badge(_ type: String) {
        let label: String
        let color: UIColor
        switch type {
        case "ens":     label = "⬡ ENS";    color = UIColor(red: 0.91, green: 0.27, blue: 0.38, alpha: 1)
        case "pixel":   label = "⬡ .pixel"; color = UIColor(red: 0.91, green: 0.27, blue: 0.38, alpha: 1)
        case "ipfs":    label = "⬡ IPFS";   color = UIColor(red: 0.91, green: 0.27, blue: 0.38, alpha: 1)
        case "bit":     label = "⬡ .bit";   color = UIColor(red: 0.91, green: 0.27, blue: 0.38, alpha: 1)
        default:        label = "🌐";        color = UIColor(red: 0.06, green: 0.20, blue: 0.38, alpha: 1)
        }
        badgeWeb3.text = label
        badgeWeb3.backgroundColor = color
    }

    @objc private func goBack() {
        if webView.canGoBack { webView.goBack() }
    }
    @objc private func goForward() {
        if webView.canGoForward { webView.goForward() }
    }
    @objc private func refresh() {
        webView.reload()
    }

    // MARK: - WKNavigationDelegate
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        progressBar.setProgress(0.3, animated: true)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        progressBar.setProgress(1.0, animated: true)
        currentUrl = webView.url?.absoluteString ?? ""
        urlBar.text = currentUrl
        addHistory(currentUrl)

        // Inject NOP bridge JS
        let js = """
        (function() {
            if (window.__nop_injected) return;
            window.__nop_injected = true;
            window.NOP = {
                resolve: u => fetch('\(nopBridge)/resolve?url='+encodeURIComponent(u)).then(r=>r.json()),
                checkUrl: u => fetch('\(nopBridge)/check_url?url='+encodeURIComponent(u)).then(r=>r.json()),
                walletStatus: () => fetch('\(nopBridge)/wallet/status').then(r=>r.json()),
                walletBalance: a => fetch('\(nopBridge)/wallet/balance'+(a?'?address='+a:'')).then(r=>r.json()),
                signTx: t => fetch('\(nopBridge)/sign_tx', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(t)}).then(r=>r.json())
            };
            console.log('[NOP] Bridge OK');
        })();
        """
        webView.evaluateJavaScript(js)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        progressBar.setProgress(0, animated: false)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url?.absoluteString else {
            decisionHandler(.allow)
            return
        }

        // Check ad/tracker via bridge
        guard let encoded = url.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let checkUrl = URL(string: "\(nopBridge)/check_url?url=\(encoded)") else {
            decisionHandler(.allow)
            return
        }

        URLSession.shared.dataTask(with: checkUrl) { data, _, _ in
            if let data = data,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               json["blocked"] as? Bool == true {
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
        }.resume()
    }

    // MARK: - Menu
    @objc private func showMenu() {
        let alert = UIAlertController(title: "NOP Browser", message: nil, preferredStyle: .actionSheet)
        alert.addAction(UIAlertAction(title: "⭐ Favoris", style: .default) { [weak self] _ in self?.showBookmarks() })
        alert.addAction(UIAlertAction(title: "⌛ Historique", style: .default) { [weak self] _ in self?.showHistory() })
        alert.addAction(UIAlertAction(title: "⚙ Paramètres", style: .default) { [weak self] _ in self?.showSettings() })
        alert.addAction(UIAlertAction(title: "💳 Wallet", style: .default) { [weak self] _ in self?.showWallet() })
        alert.addAction(UIAlertAction(title: "🧹 Clear Cache", style: .destructive) { [weak self] _ in self?.clearCache() })
        alert.addAction(UIAlertAction(title: "Annuler", style: .cancel))
        present(alert, animated: true)
    }

    private func showBookmarks() {
        let list = bookmarks.map { $0["url"] ?? "" }.joined(separator: "\n")
        let alert = UIAlertController(title: "⭐ Favoris", message: list.isEmpty ? "Aucun" : list,
                                       preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        alert.addAction(UIAlertAction(title: "Ajouter", style: .default) { [weak self] _ in
            guard let self = self, !self.currentUrl.isEmpty else { return }
            self.bookmarks.append(["url": self.currentUrl, "title": self.webView.title ?? ""])
            let alert2 = UIAlertController(title: "Favori", message: "Page ajoutée", preferredStyle: .alert)
            alert2.addAction(UIAlertAction(title: "OK", style: .default))
            self.present(alert2, animated: true)
        })
        present(alert, animated: true)
    }

    private func showHistory() {
        let list = history.suffix(20).map { $0["url"] ?? "" }.joined(separator: "\n")
        let alert = UIAlertController(title: "⌛ Historique", message: list.isEmpty ? "Aucun" : list,
                                       preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        alert.addAction(UIAlertAction(title: "Effacer", style: .destructive) { [weak self] _ in
            self?.history = []
        })
        present(alert, animated: true)
    }

    private func showSettings() {
        let alert = UIAlertController(title: "⚙ Paramètres", message: nil, preferredStyle: .alert)
        alert.addTextField { tf in
            tf.placeholder = "Page d'accueil"
            tf.text = "https://duckduckgo.com"
        }
        alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in
            if let text = alert.textFields?.first?.text, !text.isEmpty {
                self?.loadUrl(text)
            }
        })
        alert.addAction(UIAlertAction(title: "Annuler", style: .cancel))
        present(alert, animated: true)
    }

    private func showWallet() {
        guard let url = URL(string: "\(nopBridge)/wallet/status") else { return }
        URLSession.shared.dataTask(with: url) { [weak self] data, _, _ in
            let status: String
            if let data = data,
               let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               json["available"] as? Bool == true {
                status = "✅ Wallet connecté"
            } else {
                status = "❌ Wallet non disponible"
            }
            DispatchQueue.main.async {
                let alert = UIAlertController(title: "💳 Wallet", message: status, preferredStyle: .alert)
                alert.addAction(UIAlertAction(title: "OK", style: .default))
                self?.present(alert, animated: true)
            }
        }.resume()
    }

    private func clearCache() {
        let types = WKWebsiteDataStore.allWebsiteDataTypes()
        let since = Date.distantPast
        WKWebsiteDataStore.default().removeData(ofTypes: types, modifiedSince: since) { [weak self] in
            let alert = UIAlertController(title: "🧹", message: "Cache effacé", preferredStyle: .alert)
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            self?.present(alert, animated: true)
        }
    }

    private func addHistory(_ url: String) {
        history.append(["url": url, "ts": ISO8601DateFormatter().string(from: Date())])
        if history.count > 500 { history.removeFirst(100) }
    }
}

// MARK: - UITextFieldDelegate
extension NopViewController: UITextFieldDelegate {
    func textFieldShouldReturn(_ textField: UITextField) -> Bool {
        textField.resignFirstResponder()
        if let text = textField.text {
            loadUrl(text)
        }
        return true
    }
}
