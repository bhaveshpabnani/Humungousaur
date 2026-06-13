cask "humungousaur" do
  version "0.1.4"
  sha256 "48873267762f3b70684fc44cad4b85edb0296f4b030e55449a12a034de1d6a3d"

  url "https://github.com/bhaveshpabnani/Humungousaur/releases/download/v#{version}/Humungousaur-macOS.pkg",
      verified: "github.com/bhaveshpabnani/Humungousaur/"
  name "Humungousaur"
  desc "Local-first desktop agent runtime with native apps, collectors, approvals, and memory"
  homepage "https://github.com/bhaveshpabnani/Humungousaur"

  pkg "Humungousaur-macOS.pkg"

  uninstall pkgutil: "ai.humungousaur.mac.installer"

  zap trash: [
    "~/Library/Application Support/Humungousaur",
    "~/Library/Preferences/ai.humungousaur.mac.plist",
    "~/Library/Saved Application State/ai.humungousaur.mac.savedState",
  ]

  caveats do
    <<~EOS
      This early-access package installs Humungousaur.app and the bundled local runtime.

      Public production macOS releases should be Developer ID signed and notarized.
      Until that certificate/notarization flow is complete, macOS Gatekeeper may warn
      that Apple cannot verify the package.
    EOS
  end
end
