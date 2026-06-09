# Master list of supported tickers (stocks / ETFs / crypto) used by the
# autocomplete dropdown. Served via GET /api/symbols.

US_STOCKS = [
    # ── Tech & Software (mega-caps + cloud + cyber + AI) ────────────────────
    ("AAPL", "Apple Inc."), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet (Google) Class A"),
    ("GOOG", "Alphabet (Google) Class C"), ("AMZN", "Amazon"), ("NVDA", "NVIDIA"),
    ("META", "Meta Platforms"), ("NFLX", "Netflix"), ("AMD", "Advanced Micro Devices"),
    ("INTC", "Intel"), ("CRM", "Salesforce"), ("ORCL", "Oracle"), ("ADBE", "Adobe"),
    ("CSCO", "Cisco Systems"), ("AVGO", "Broadcom"), ("QCOM", "Qualcomm"),
    ("TXN", "Texas Instruments"), ("INTU", "Intuit"), ("NOW", "ServiceNow"),
    ("IBM", "IBM"), ("WDAY", "Workday"), ("PANW", "Palo Alto Networks"),
    ("CRWD", "CrowdStrike"), ("ZS", "Zscaler"), ("FTNT", "Fortinet"), ("SNOW", "Snowflake"),
    ("DDOG", "Datadog"), ("MDB", "MongoDB"), ("CFLT", "Confluent"), ("NET", "Cloudflare"),
    ("TWLO", "Twilio"), ("DOCU", "DocuSign"), ("ZM", "Zoom Video"), ("OKTA", "Okta"),
    ("HUBS", "HubSpot"), ("TEAM", "Atlassian"), ("VEEV", "Veeva Systems"),
    ("ADSK", "Autodesk"), ("ANSS", "Ansys"), ("MU", "Micron Technology"),
    ("AMAT", "Applied Materials"), ("LRCX", "Lam Research"), ("KLAC", "KLA"),
    ("MRVL", "Marvell Technology"), ("ON", "ON Semiconductor"), ("MPWR", "Monolithic Power"),
    ("ADI", "Analog Devices"), ("MCHP", "Microchip Technology"), ("SWKS", "Skyworks Solutions"),
    ("PLTR", "Palantir Technologies"), ("U", "Unity Software"), ("AI", "C3.ai"),
    ("PATH", "UiPath"), ("ESTC", "Elastic"), ("FRSH", "Freshworks"), ("S", "SentinelOne"),
    ("GTLB", "GitLab"), ("PD", "PagerDuty"), ("BILL", "Bill.com"), ("DT", "Dynatrace"),
    ("APPN", "Appian"), ("RBLX", "Roblox"), ("EA", "Electronic Arts"),
    ("TTWO", "Take-Two Interactive"), ("RNG", "RingCentral"), ("BOX", "Box"),

    # ── E-commerce / Internet / Media ───────────────────────────────────────
    ("SHOP", "Shopify"), ("MELI", "MercadoLibre"), ("EBAY", "eBay"), ("ETSY", "Etsy"),
    ("PINS", "Pinterest"), ("SNAP", "Snap"), ("SPOT", "Spotify"), ("ROKU", "Roku"),
    ("DASH", "DoorDash"), ("UBER", "Uber Technologies"), ("LYFT", "Lyft"),
    ("ABNB", "Airbnb"), ("BKNG", "Booking Holdings"), ("EXPE", "Expedia"),
    ("CVNA", "Carvana"), ("OPEN", "Opendoor"), ("Z", "Zillow"), ("RDFN", "Redfin"),
    ("PTON", "Peloton"), ("MTCH", "Match Group"), ("BMBL", "Bumble"),
    ("WBD", "Warner Bros. Discovery"), ("PARA", "Paramount Global"), ("DIS", "Walt Disney"),
    ("CMCSA", "Comcast"), ("T", "AT&T"), ("VZ", "Verizon Communications"),
    ("TMUS", "T-Mobile US"), ("CHTR", "Charter Communications"),

    # ── Fintech / Payments / Crypto-adjacent ────────────────────────────────
    ("V", "Visa"), ("MA", "Mastercard"), ("PYPL", "PayPal"), ("SQ", "Block (Square)"),
    ("AXP", "American Express"), ("COIN", "Coinbase"), ("HOOD", "Robinhood Markets"),
    ("SOFI", "SoFi Technologies"), ("AFRM", "Affirm Holdings"), ("UPST", "Upstart"),
    ("LC", "LendingClub"), ("FIS", "Fidelity National Information"), ("FISV", "Fiserv"),
    ("GPN", "Global Payments"), ("DFS", "Discover Financial"), ("ALLY", "Ally Financial"),
    ("MSCI", "MSCI Inc"), ("CME", "CME Group"), ("ICE", "Intercontinental Exchange"),
    ("NDAQ", "Nasdaq Inc"), ("SCHW", "Charles Schwab"), ("MKTX", "MarketAxess"),

    # ── Banks ────────────────────────────────────────────────────────────────
    ("JPM", "JPMorgan Chase"), ("BAC", "Bank of America"), ("WFC", "Wells Fargo"),
    ("C", "Citigroup"), ("GS", "Goldman Sachs"), ("MS", "Morgan Stanley"),
    ("USB", "U.S. Bancorp"), ("PNC", "PNC Financial"), ("TFC", "Truist Financial"),
    ("COF", "Capital One Financial"), ("BK", "Bank of New York Mellon"), ("STT", "State Street"),
    ("BLK", "BlackRock"), ("KKR", "KKR & Co"), ("APO", "Apollo Global Management"),
    ("BX", "Blackstone"), ("CG", "Carlyle Group"), ("AMP", "Ameriprise Financial"),

    # ── Insurance ────────────────────────────────────────────────────────────
    ("BRK-B", "Berkshire Hathaway B"), ("BRK-A", "Berkshire Hathaway A"),
    ("PGR", "Progressive"), ("ALL", "Allstate"), ("TRV", "Travelers"),
    ("MET", "MetLife"), ("PRU", "Prudential Financial"), ("AIG", "American International"),
    ("CB", "Chubb"), ("AFL", "Aflac"), ("HIG", "Hartford Financial"), ("MMC", "Marsh McLennan"),
    ("AON", "Aon"), ("WTW", "Willis Towers Watson"),

    # ── Healthcare: Pharma & Biotech ────────────────────────────────────────
    ("JNJ", "Johnson & Johnson"), ("LLY", "Eli Lilly"), ("UNH", "UnitedHealth Group"),
    ("PFE", "Pfizer"), ("MRK", "Merck"), ("ABBV", "AbbVie"), ("BMY", "Bristol-Myers Squibb"),
    ("AMGN", "Amgen"), ("GILD", "Gilead Sciences"), ("MRNA", "Moderna"),
    ("BIIB", "Biogen"), ("REGN", "Regeneron"), ("VRTX", "Vertex Pharmaceuticals"),
    ("CVS", "CVS Health"), ("CI", "Cigna"), ("HUM", "Humana"), ("ELV", "Elevance Health"),
    ("ABT", "Abbott Laboratories"), ("TMO", "Thermo Fisher Scientific"), ("DHR", "Danaher"),
    ("MDT", "Medtronic"), ("ISRG", "Intuitive Surgical"), ("BSX", "Boston Scientific"),
    ("SYK", "Stryker"), ("EW", "Edwards Lifesciences"), ("ZTS", "Zoetis"),
    ("ILMN", "Illumina"), ("IDXX", "IDEXX Laboratories"), ("DXCM", "Dexcom"),
    ("ALGN", "Align Technology"), ("HCA", "HCA Healthcare"), ("MCK", "McKesson"),
    ("COR", "Cencora"), ("CAH", "Cardinal Health"), ("BAX", "Baxter International"),
    ("BDX", "Becton Dickinson"), ("RMD", "ResMed"), ("EXAS", "Exact Sciences"),

    # ── Consumer Discretionary: Retail / Restaurants / Autos / Travel ───────
    ("HD", "Home Depot"), ("LOW", "Lowe's Companies"), ("TGT", "Target"),
    ("COST", "Costco Wholesale"), ("WMT", "Walmart"), ("TJX", "TJX Companies"),
    ("BBY", "Best Buy"), ("DG", "Dollar General"), ("DLTR", "Dollar Tree"),
    ("ROST", "Ross Stores"), ("ULTA", "Ulta Beauty"), ("LULU", "Lululemon Athletica"),
    ("NKE", "Nike"), ("SBUX", "Starbucks"), ("MCD", "McDonald's"), ("CMG", "Chipotle Mexican Grill"),
    ("YUM", "Yum Brands"), ("DPZ", "Domino's Pizza"), ("SHAK", "Shake Shack"),
    ("CAVA", "CAVA Group"), ("BROS", "Dutch Bros"), ("WING", "Wingstop"),
    ("F", "Ford Motor"), ("GM", "General Motors"), ("TSLA", "Tesla"), ("RIVN", "Rivian Automotive"),
    ("LCID", "Lucid Group"), ("STLA", "Stellantis"), ("TM", "Toyota Motor"),
    ("HMC", "Honda Motor"), ("HOG", "Harley-Davidson"),
    ("DKNG", "DraftKings"), ("PENN", "PENN Entertainment"), ("MGM", "MGM Resorts"),
    ("LVS", "Las Vegas Sands"), ("WYNN", "Wynn Resorts"), ("CZR", "Caesars Entertainment"),
    ("RCL", "Royal Caribbean Cruises"), ("CCL", "Carnival"), ("NCLH", "Norwegian Cruise Line"),
    ("MAR", "Marriott International"), ("HLT", "Hilton Worldwide"), ("H", "Hyatt Hotels"),
    ("UAL", "United Airlines"), ("DAL", "Delta Air Lines"), ("AAL", "American Airlines"),
    ("LUV", "Southwest Airlines"), ("ALK", "Alaska Air Group"),

    # ── Consumer Staples ────────────────────────────────────────────────────
    ("PG", "Procter & Gamble"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"),
    ("MDLZ", "Mondelez International"), ("PM", "Philip Morris International"),
    ("MO", "Altria Group"), ("KHC", "Kraft Heinz"), ("GIS", "General Mills"),
    ("K", "Kellanova"), ("CL", "Colgate-Palmolive"), ("KMB", "Kimberly-Clark"),
    ("EL", "Estée Lauder"), ("CHD", "Church & Dwight"), ("SJM", "J.M. Smucker"),
    ("HSY", "Hershey"), ("MKC", "McCormick"), ("CAG", "ConAgra Brands"),
    ("CPB", "Campbell Soup"), ("STZ", "Constellation Brands"), ("BUD", "Anheuser-Busch InBev"),
    ("DEO", "Diageo"), ("MNST", "Monster Beverage"), ("KDP", "Keurig Dr Pepper"),
    ("ADM", "Archer-Daniels-Midland"), ("TSN", "Tyson Foods"),

    # ── Industrials: Aerospace, Defense, Machinery, Transport ───────────────
    ("BA", "Boeing"), ("LMT", "Lockheed Martin"), ("RTX", "RTX Corp"),
    ("NOC", "Northrop Grumman"), ("GD", "General Dynamics"), ("HII", "Huntington Ingalls"),
    ("LHX", "L3Harris Technologies"), ("TXT", "Textron"), ("GE", "GE Aerospace"),
    ("CAT", "Caterpillar"), ("DE", "Deere & Co"), ("HON", "Honeywell"),
    ("MMM", "3M"), ("EMR", "Emerson Electric"), ("ETN", "Eaton"), ("ITW", "Illinois Tool Works"),
    ("PH", "Parker-Hannifin"), ("ROK", "Rockwell Automation"), ("CMI", "Cummins"),
    ("PCAR", "PACCAR"), ("UPS", "United Parcel Service"), ("FDX", "FedEx"),
    ("CHRW", "C.H. Robinson"), ("EXPD", "Expeditors International"), ("J", "Jacobs Solutions"),
    ("URI", "United Rentals"), ("WM", "Waste Management"), ("RSG", "Republic Services"),
    ("CSX", "CSX Corp"), ("NSC", "Norfolk Southern"), ("UNP", "Union Pacific"),
    ("ODFL", "Old Dominion Freight Line"), ("XPO", "XPO Inc"),

    # ── Energy: Oil & Gas, Renewables ───────────────────────────────────────
    ("XOM", "Exxon Mobil"), ("CVX", "Chevron"), ("COP", "ConocoPhillips"),
    ("EOG", "EOG Resources"), ("PXD", "Pioneer Natural Resources"), ("MPC", "Marathon Petroleum"),
    ("PSX", "Phillips 66"), ("VLO", "Valero Energy"), ("OXY", "Occidental Petroleum"),
    ("SLB", "Schlumberger"), ("HAL", "Halliburton"), ("BKR", "Baker Hughes"),
    ("HES", "Hess Corp"), ("DVN", "Devon Energy"), ("FANG", "Diamondback Energy"),
    ("CTRA", "Coterra Energy"), ("APA", "APA Corp"), ("EQT", "EQT Corp"),
    ("ENPH", "Enphase Energy"), ("FSLR", "First Solar"), ("RUN", "Sunrun"),
    ("PLUG", "Plug Power"), ("BE", "Bloom Energy"),

    # ── Materials: Chemicals, Metals, Mining ────────────────────────────────
    ("LIN", "Linde"), ("APD", "Air Products"), ("SHW", "Sherwin-Williams"),
    ("ECL", "Ecolab"), ("DD", "DuPont de Nemours"), ("DOW", "Dow Inc"),
    ("PPG", "PPG Industries"), ("LYB", "LyondellBasell"), ("CF", "CF Industries"),
    ("NEM", "Newmont"), ("GOLD", "Barrick Gold"), ("FCX", "Freeport-McMoRan"),
    ("AA", "Alcoa"), ("STLD", "Steel Dynamics"), ("NUE", "Nucor"), ("X", "United States Steel"),
    ("CLF", "Cleveland-Cliffs"), ("MP", "MP Materials"), ("RIO", "Rio Tinto"),
    ("BHP", "BHP Group"), ("VALE", "Vale SA"),

    # ── Real Estate (REITs) ─────────────────────────────────────────────────
    ("AMT", "American Tower"), ("PLD", "Prologis"), ("EQIX", "Equinix"),
    ("CCI", "Crown Castle"), ("SPG", "Simon Property Group"), ("WELL", "Welltower"),
    ("PSA", "Public Storage"), ("O", "Realty Income"), ("DLR", "Digital Realty"),
    ("AVB", "AvalonBay Communities"), ("EQR", "Equity Residential"), ("VTR", "Ventas"),
    ("EXR", "Extra Space Storage"), ("ARE", "Alexandria Real Estate"), ("BXP", "Boston Properties"),
    ("VICI", "VICI Properties"), ("UDR", "UDR Inc"), ("MAA", "Mid-America Apartment"),
    ("ESS", "Essex Property Trust"), ("CPT", "Camden Property Trust"),

    # ── Utilities ───────────────────────────────────────────────────────────
    ("NEE", "NextEra Energy"), ("SO", "Southern Co"), ("DUK", "Duke Energy"),
    ("D", "Dominion Energy"), ("AEP", "American Electric Power"), ("SRE", "Sempra"),
    ("EXC", "Exelon"), ("XEL", "Xcel Energy"), ("PEG", "Public Service Enterprise"),
    ("ED", "Consolidated Edison"), ("WEC", "WEC Energy Group"), ("ES", "Eversource Energy"),
    ("AWK", "American Water Works"), ("PCG", "PG&E Corp"), ("EIX", "Edison International"),
    ("PPL", "PPL Corp"), ("CMS", "CMS Energy"), ("DTE", "DTE Energy"),

    # ── International / ADRs (popular) ──────────────────────────────────────
    ("BABA", "Alibaba Group (China)"), ("TCEHY", "Tencent Holdings (China)"),
    ("TSM", "Taiwan Semiconductor"), ("ASML", "ASML Holding (Netherlands)"),
    ("SAP", "SAP SE (Germany)"), ("SONY", "Sony Group (Japan)"),
    ("NVO", "Novo Nordisk (Denmark)"), ("RY", "Royal Bank of Canada"),
    ("TD", "Toronto-Dominion Bank"), ("HSBC", "HSBC Holdings (UK)"),
    ("BP", "BP plc (UK)"), ("SHEL", "Shell plc (UK)"), ("SIE", "Siemens (Germany)"),
    ("LVMUY", "LVMH (France)"), ("NESN", "Nestle (Switzerland)"),
    ("RHHBY", "Roche Holdings (Switzerland)"), ("NVS", "Novartis (Switzerland)"),
    ("AZN", "AstraZeneca (UK)"), ("GSK", "GSK (UK)"), ("UL", "Unilever (UK)"),
    ("DEO", "Diageo (UK)"), ("PDD", "PDD Holdings (China)"), ("JD", "JD.com (China)"),
    ("NIO", "NIO Inc (China)"), ("XPEV", "XPeng (China)"), ("LI", "Li Auto (China)"),
    ("BIDU", "Baidu (China)"), ("NTES", "NetEase (China)"), ("MFC", "Manulife Financial"),
    ("BNS", "Bank of Nova Scotia"), ("CNQ", "Canadian Natural Resources"),
    ("ENB", "Enbridge"), ("CNI", "Canadian National Railway"),
]

ETFS = [
    ("SPY",  "S&P 500 ETF (SPDR)"),         ("QQQ",  "Nasdaq 100 ETF (Invesco)"),
    ("IWM",  "Russell 2000 ETF"),            ("VTI",  "Total Stock Market ETF"),
    ("VOO",  "S&P 500 ETF (Vanguard)"),      ("VEA",  "Developed Markets ETF (Vanguard)"),
    ("VWO",  "Emerging Markets ETF (Vanguard)"), ("EFA", "MSCI EAFE ETF (iShares)"),
    ("EEM",  "MSCI Emerging Markets ETF"),   ("DIA",  "Dow Jones Industrial ETF (SPDR)"),
    ("ARKK", "ARK Innovation ETF"),          ("ARKQ", "ARK Autonomous Technology ETF"),
    ("ARKG", "ARK Genomic Revolution ETF"),  ("ARKF", "ARK Fintech Innovation ETF"),
    ("ARKW", "ARK Next Generation Internet ETF"),
    ("GLD",  "Gold ETF (SPDR)"),             ("SLV",  "Silver ETF (iShares)"),
    ("USO",  "Oil ETF (USCF)"),              ("UNG",  "Natural Gas ETF"),
    ("TLT",  "20+ Year Treasury Bond ETF"),  ("IEF",  "7-10 Year Treasury Bond ETF"),
    ("SHY",  "1-3 Year Treasury Bond ETF"),  ("BIL",  "Bloomberg 1-3 Month T-Bill ETF"),
    ("AGG",  "US Aggregate Bond ETF"),       ("BND",  "Total Bond Market ETF (Vanguard)"),
    ("HYG",  "High Yield Corporate Bond ETF"), ("LQD", "Investment Grade Corporate Bond ETF"),
    ("XLF",  "Financial Sector ETF"),        ("XLK",  "Technology Sector ETF"),
    ("XLE",  "Energy Sector ETF"),           ("XLV",  "Healthcare Sector ETF"),
    ("XLI",  "Industrials Sector ETF"),      ("XLY",  "Consumer Discretionary Sector ETF"),
    ("XLP",  "Consumer Staples Sector ETF"), ("XLU",  "Utilities Sector ETF"),
    ("XLB",  "Materials Sector ETF"),        ("XLRE", "Real Estate Sector ETF"),
    ("XLC",  "Communication Services Sector ETF"),
    ("SOXX", "Semiconductor ETF (iShares)"), ("SMH",  "VanEck Semiconductor ETF"),
    ("VXX",  "Volatility ETF (iPath)"),      ("UVXY", "Ultra VIX Short-Term Futures ETF"),
    ("SQQQ", "ProShares UltraPro Short QQQ"),("TQQQ", "ProShares UltraPro QQQ"),
    ("SPXU", "ProShares UltraPro Short S&P500"), ("UPRO", "ProShares UltraPro S&P500"),
    ("SOXL", "Direxion Semi Bull 3x"),       ("SOXS", "Direxion Semi Bear 3x"),
    ("TNA",  "Direxion Small Cap Bull 3x"),  ("TZA",  "Direxion Small Cap Bear 3x"),
    ("JETS", "US Global Jets ETF"),          ("ICLN", "Global Clean Energy ETF (iShares)"),
    ("BOTZ", "Global X Robotics & AI ETF"),  ("HACK", "ETFMG Prime Cyber Security ETF"),
    ("VNQ",  "Vanguard Real Estate ETF"),    ("KRE",  "SPDR Regional Banking ETF"),
    ("IBB",  "iShares Biotechnology ETF"),   ("XBI",  "SPDR S&P Biotech ETF"),
]

CRYPTO = [
    ("BTC-USD",   "Bitcoin"),       ("ETH-USD",   "Ethereum"),
    ("SOL-USD",   "Solana"),        ("BNB-USD",   "Binance Coin"),
    ("XRP-USD",   "Ripple"),        ("ADA-USD",   "Cardano"),
    ("AVAX-USD",  "Avalanche"),     ("DOGE-USD",  "Dogecoin"),
    ("MATIC-USD", "Polygon"),       ("DOT-USD",   "Polkadot"),
    ("LINK-USD",  "Chainlink"),     ("UNI-USD",   "Uniswap"),
    ("ATOM-USD",  "Cosmos"),        ("ALGO-USD",  "Algorand"),
    ("NEAR-USD",  "NEAR Protocol"), ("FTM-USD",   "Fantom"),
    ("SAND-USD",  "The Sandbox"),   ("MANA-USD",  "Decentraland"),
    ("APE-USD",   "ApeCoin"),       ("CRO-USD",   "Cronos"),
    ("LTC-USD",   "Litecoin"),      ("BCH-USD",   "Bitcoin Cash"),
    ("XLM-USD",   "Stellar"),       ("VET-USD",   "VeChain"),
    ("THETA-USD", "Theta Network"), ("FIL-USD",   "Filecoin"),
    ("AAVE-USD",  "Aave"),          ("COMP-USD",  "Compound"),
    ("INJ-USD",   "Injective"),     ("TIA-USD",   "Celestia"),
    ("SUI-USD",   "Sui"),           ("ARB-USD",   "Arbitrum"),
    ("OP-USD",    "Optimism"),      ("RUNE-USD",  "THORChain"),
]


def _dedup(items):
    """De-dupe by ticker, preserving first occurrence."""
    seen, out = set(), []
    for tkr, name in items:
        if tkr in seen:
            continue
        seen.add(tkr)
        out.append((tkr, name))
    return out


def get_all_symbols():
    """Return the full autocomplete dataset as a list of dicts."""
    out = []
    for tkr, name in _dedup(US_STOCKS):
        out.append({"ticker": tkr, "name": name, "type": "Stock"})
    for tkr, name in _dedup(ETFS):
        out.append({"ticker": tkr, "name": name, "type": "ETF"})
    for tkr, name in _dedup(CRYPTO):
        out.append({"ticker": tkr, "name": name, "type": "Crypto"})
    return out
