/* Shared kiosk copy. Product names and ingredient names are left unchanged. */
(function () {
  const ui = {
    viewCart: ['View cart', 'Tingnan ang cart', 'Tan-awa ang cart'],
    productInfo: ['Product information', 'Impormasyon ng produkto', 'Impormasyon sa produkto'],
    unavailable: ['Unavailable', 'Hindi available', 'Dili available'],
    welcomeChoice: ['How can we help?', 'Paano ka namin matutulungan?', 'Unsaon namo pagtabang nimo?'],
    welcomeChoiceHelp: ['Choose a medicine or tell us how you feel.', 'Pumili ng gamot o sabihin ang iyong nararamdaman.', 'Pilia ang tambal o isulti ang imong gibati.'],
    browseMedicines: ['Browse medicines', 'Pumili ng gamot', 'Pilia ang tambal'],
    browseMedicinesHelp: ['View medicines, prices and stock. Add your selection to the cart.', 'Tingnan ang mga gamot, presyo at stock. Idagdag ang napili sa cart.', 'Tan-awa ang tambal, presyo ug stock. Idugang ang napili sa cart.'],
    describeSymptoms: ['Describe symptoms', 'Ilarawan ang sintomas', 'Isulti ang sintomas'],
    describeSymptomsHelp: ['Answer a few questions to see suitable options and safety guidance.', 'Sagutin ang ilang tanong para makita ang angkop na mga opsyon at gabay.', 'Tubaga ang pipila ka pangutana aron makita ang angay nga mga kapilian ug giya.'],
    openCatalog: ['Open catalog →', 'Buksan ang catalog →', 'Ablihi ang catalog →'],
    startConsultation: ['Start consultation →', 'Simulan ang konsultasyon →', 'Sugdi ang konsultasyon →'],
    searchMedicines: ['Search medicines', 'Maghanap ng gamot', 'Pangitaa ang tambal'],
    catalogNotice: ['Product information is not a diagnosis. Check the package and ask a pharmacist if unsure.', 'Hindi diagnosis ang impormasyon ng produkto. Suriin ang pakete at magtanong sa pharmacist kung hindi sigurado.', 'Dili diagnosis ang impormasyon sa produkto. Susiha ang pakete ug pangutana sa pharmacist kung dili sigurado.'],
    productNotCarried: ['This product is not carried here', 'Walang angkop na produkto rito', 'Walay angay nga produkto dinhi'],
    unstockedSafety: ['Get urgent medical help for severe pain, heavy bleeding, breathing difficulty, spreading infection or sudden vision changes.', 'Humingi agad ng medikal na tulong kung matindi ang sakit, malakas ang pagdurugo, hirap huminga, kumakalat ang impeksiyon o biglang nagbago ang paningin.', 'Pangayo dayon og medikal nga tabang kung grabe ang sakit, kusog ang pagdugo, lisod ginhawa, nagkatag ang impeksiyon o kalit nausab ang panan-aw.'],
    perUnit: ['per unit', 'bawat piraso', 'matag piraso'],
    pharmacistReview: ['Pharmacist review needed', 'Kailangang suriin ng pharmacist', 'Kinahanglan susihon sa pharmacist'],
    viewDetails: ['View details', 'Tingnan ang detalye', 'Tan-awa ang detalye'],
    noProductsFound: ['No matching products. Try a brand or ingredient name.', 'Walang katugmang produkto. Subukan ang pangalan ng brand o sangkap.', 'Walay katugbang nga produkto. Sulayi ang brand o sangkap.'],
    uses: ['Uses', 'Mga gamit', 'Mga gamit'], instructions: ['Instructions', 'Mga tagubilin', 'Mga panudlo'], warnings: ['Warnings', 'Mga babala', 'Mga pahimangno'],
    askPharmacistIf: ['Ask a pharmacist if any of these apply', 'Magtanong sa pharmacist kung may alinman dito', 'Pangutana sa pharmacist kung adunay bisan usa niini'],
    catalogInstructions: ['Follow the exact package directions. Ask a pharmacist about dose, interactions and suitability; avoid duplicate ingredients.', 'Sundin ang tagubilin sa pakete. Magtanong sa pharmacist tungkol sa dosis, interactions at angkop na paggamit; iwasan ang magkakaparehong sangkap.', 'Sunda ang panudlo sa pakete. Pangutana sa pharmacist bahin sa dosis, interactions ug angay nga paggamit; likayi ang managsamang sangkap.'],
    productPhotoNote: ['Product reference photo; packaging may vary. Check the actual supplied label.', 'Larawan ng produkto; maaaring mag-iba ang pakete. Suriin ang aktuwal na label.', 'Hulagway sa produkto; mahimong lahi ang pakete. Susiha ang aktuwal nga label.'],
    addToCart: ['Add to cart', 'Idagdag sa cart', 'Idugang sa cart'], buyNow: ['Buy now', 'Bilhin ngayon', 'Palita karon'],
    enterValidAge: ['Enter a whole-number age from 1 to 120.', 'Ilagay ang edad mula 1 hanggang 120.', 'Isulod ang edad gikan sa 1 hangtod 120.'],
    ageNotSuitable: ['This product is not suitable for the entered age. Ask a pharmacist.', 'Hindi angkop ang produktong ito sa inilagay na edad. Magtanong sa pharmacist.', 'Dili angay kini sa gisulod nga edad. Pangutana sa pharmacist.'],
    supplementPending: ['Nutrabliss is listed for information. Local label and dispensing-slot verification are required before kiosk purchase.', 'Impormasyon lamang ang listing ng Nutrabliss. Kailangang ma-verify ang lokal na label at dispensing slot bago mabili rito.', 'Para sa impormasyon ang listing sa Nutrabliss. Kinahanglan ma-verify ang lokal nga label ug dispensing slot sa dili pa mapalit dinhi.'],
    retry: ['Try again', 'Subukan muli', 'Sulayi pag-usab'],
    back: ['Back', 'Bumalik', 'Balik'], cancel: ['Cancel', 'Kanselahin', 'Kanselahon'],
    confirm: ['Confirm', 'Kumpirmahin', 'Kumpirmaha'], results: ['Results', 'Resulta', 'Resulta'],
    symptoms: ['Symptoms', 'Mga sintomas', 'Mga sintomas'],
    whyAge: ['Why do we ask your age?', 'Bakit namin tinatanong ang edad?', 'Nganong mangutana mi sa imong edad?'],
    ageHelp: ['Some medicines have age limits. Your age helps us show suitable options.', 'May limitasyon sa edad ang ilang gamot. Ginagamit ang edad mo upang magpakita ng angkop na gamot.', 'Ang ubang tambal adunay limitasyon sa edad. Gigamit ang imong edad aron ipakita ang angay nga tambal.'],
    about: ['About Mendo', 'Tungkol sa Mendo', 'Bahin sa Mendo'],
    aboutBody: ['Mendo suggests available medicines based on your symptoms and age.', 'Nagmumungkahi ang Mendo ng mga gamot batay sa iyong sintomas at edad.', 'Ang Mendo mosugyot og mga tambal base sa imong sintomas ug edad.'],
    aboutLanguages: ['Describe your symptoms in English, Tagalog, Bisaya, or a mix of these languages.', 'Ilarawan ang iyong sintomas sa English, Tagalog, Bisaya, o halo ng mga ito.', 'Isulti ang imong sintomas sa English, Tagalog, Bisaya, o sagol niini.'],
    aboutNote: ['This is not a diagnosis. Ask a doctor or pharmacist about severe or lasting symptoms.', 'Hindi ito diagnosis. Kumonsulta sa doktor o pharmacist kung malubha o tumatagal ang sintomas.', 'Dili kini diagnosis. Pangutana sa doktor o pharmacist kung grabe o dugay mawala ang sintomas.'],
    languages: ['Supported languages', 'Mga suportadong wika', 'Mga suportadong pinulongan'],
    languageHelp: ['Choose the language for the screen. You can describe symptoms in any supported language.', 'Piliin ang wika ng screen. Maaari mong ilarawan ang sintomas sa alinmang suportadong wika.', 'Pilia ang pinulongan sa screen. Pwede nimo isulti ang sintomas sa bisan unsang suportadong pinulongan.'],
    voiceHelp: ['Tap the microphone and speak naturally.', 'Pindutin ang mikropono at magsalita.', 'Pindota ang mikropono ug isulti ang imong gibati.'],
    speak: ['Tap to speak', 'Pindutin upang magsalita', 'Pindota aron mosulti'],
    detecting: ['Checking your symptoms…', 'Sinusuri ang iyong sintomas…', 'Gisusi ang imong sintomas…'],
    analyzing: ['Reviewing your symptoms…', 'Sinusuri ang iyong mga sagot…', 'Gisusi ang imong mga tubag…'],
    pleaseWait: ['Please wait.', 'Sandali lamang.', 'Palihug hulat.'],
    idleTitle: ['Are you still there?', 'Nariyan ka pa ba?', 'Naa pa ka diha?'],
    idleBody: ['Your session will end soon due to inactivity.', 'Malapit nang matapos ang session dahil walang aktibidad.', 'Mahuman na ang imong session kay walay kalihokan.'],
    secondsLeft: ['seconds left', 'segundo ang natitira', 'ka segundo ang nahabilin'],
    continueSession: ['Continue session', 'Ipagpatuloy ang session', 'Ipadayon ang session'],
    bestMatch: ['Select the best match.', 'Piliin ang pinakaangkop na sagot.', 'Pilia ang labing duol nga tubag.'],
    inStock: ['In stock', 'May stock', 'Adunay stock'], outOfStock: ['Out of stock', 'Walang stock', 'Walay stock'],
    buy: ['Buy', 'Bilhin', 'Palita'], slot: ['Slot', 'Slot', 'Slot'],
    notShown: ['Not shown', 'Hindi ipinakita', 'Wala gipakita'],
    minimumAge: ['Minimum age', 'Pinakamababang edad', 'Kinagamayang edad'],
    safetyExcluded: ['Excluded for safety', 'Hindi isinama para sa kaligtasan', 'Wala giapil para sa kaluwasan'],
    checkout: ['Proceed to checkout', 'Magpatuloy sa pagbabayad', 'Padayon sa pagbayad'],
    checkoutShort: ['Checkout', 'Pagbabayad', 'Pagbayad'],
    cartAdded: ['added to cart', 'idinagdag sa cart', 'gidugang sa cart'],
    tryAgain: ['Something went wrong. Please try again.', 'May problema. Subukan muli.', 'Adunay problema. Palihug sulayi pag-usab.'],
    voiceError: ['Voice input is unavailable. Please type your symptoms.', 'Hindi magamit ang voice input. I-type ang iyong sintomas.', 'Dili magamit ang mikropono karon. Palihug i-type ang imong sintomas.'],
    prolongedRunnyNose: ['Your runny nose has lasted longer than expected. Please consult a doctor or pharmacist.', 'Matagal na ang iyong sipon. Kumonsulta sa doktor o pharmacist.', 'Dugay na ang imong sip-on. Palihug pakigkita sa doktor o pharmacist.'],
    conditionSafety: ['Some medicines were excluded because of your health condition. Ask a pharmacist.', 'Hindi isinama ang ilang gamot dahil sa iyong kondisyon. Magtanong sa pharmacist.', 'Wala giapil ang ubang tambal tungod sa imong kondisyon. Pangutana sa pharmacist.'],
  };
  const flags = {
    blood_in_stool: ['Blood in stool', 'Dugo sa dumi', 'Dugo sa tae'],
    blood_vomit: ['Blood in vomit', 'Dugo sa suka', 'Dugo sa sinuka'],
    chest_pain: ['Chest pain or pressure', 'Pananakit o paninikip ng dibdib', 'Sakit o paghuot sa dughan'],
    difficulty_breathing: ['Difficulty breathing', 'Hirap huminga', 'Lisod pagginhawa'],
    dengue_warning: ['Possible dengue warning signs', 'Posibleng mga babala ng dengue', 'Posibleng mga timailhan sa dengue'],
    stroke_warning: ['Possible stroke warning signs', 'Posibleng mga babala ng stroke', 'Posibleng mga timailhan sa stroke'],
    severe_dehydration: ['Possible severe dehydration', 'Posibleng matinding kakulangan sa tubig', 'Posibleng grabeng kakulang sa tubig sa lawas'],
    pregnancy_contraindication: ['Pregnancy: ask a pharmacist before taking medicine', 'Buntis: magtanong sa pharmacist bago uminom ng gamot', 'Buntis: pangutana sa pharmacist sa dili pa motumar og tambal'],
    high_fever_prolonged: ['Very high fever (40 °C or higher)', 'Napakataas na lagnat (40 °C pataas)', 'Taas kaayo nga hilanat (40 °C o labaw pa)'],
    seizure: ['Seizure or convulsion', 'Pangingisay', 'Pagkumbulsyon'],
    loss_of_consciousness: ['Loss of consciousness', 'Pagkawala ng malay', 'Pagkawala sa panimuot'],
    severe_allergic_reaction: ['Signs of a severe allergic reaction', 'Mga palatandaan ng matinding allergy', 'Mga timailhan sa grabeng allergy'],
    rashes_breathing_difficulty: ['Rashes with difficulty breathing', 'Pantal at hirap huminga', 'Pantal ug lisod pagginhawa'],
    head_bleeding: ['Head or facial bleeding', 'Pagdurugo sa ulo o mukha', 'Pagdugo sa ulo o nawong'],
    nose_bleeding: ['Nosebleed', 'Pagdurugo ng ilong', 'Pagdugo sa ilong'],
    ear_bleeding: ['Ear bleeding', 'Pagdurugo ng tenga', 'Pagdugo sa dalunggan'],
    hemoptysis: ['Coughing up blood', 'Pag-ubo ng dugo', 'Pag-ubo og dugo'],
    blood_in_urine: ['Blood in urine', 'Dugo sa ihi', 'Dugo sa ihi'],
    hypertension_risk: ['High blood pressure: ask a medical professional before taking medicine', 'Mataas na presyon: magtanong sa doktor bago uminom ng gamot', 'Taas nga presyon: pangutana sa doktor sa dili pa motumar og tambal'],
    headache_red_flag: ['Headache warning signs require medical attention', 'Kailangang ipasuri ang mga babalang sintomas ng sakit ng ulo', 'Kinahanglan ipasusi sa doktor ang mga delikadong timailhan sa sakit sa ulo'],
  };
  flags.headache_location = flags.headache_red_flag;
  const notices = [
    ['Consult a pharmacist.', 'Kumonsulta sa pharmacist.', 'Pangutana sa pharmacist.'],
    ['Please consult a pharmacist.', 'Kumonsulta sa pharmacist.', 'Palihug pangutana sa pharmacist.'],
    ['⚠ Possible food poisoning',
      '⚠ Posibleng food poisoning o impeksiyon. Hindi inirerekomenda ang loperamide dahil hindi ito angkop sa ilang uri ng nakahahawang pagtatae. Ang probiotic, kung pinayagan ng pharmacist, ay dagdag na tulong lamang at hindi kapalit ng oral rehydration solution. Gumamit ng angkop na ORS at uminom ng ligtas na tubig. Magpatingin kung lumampas sa 2 araw, may mataas na lagnat, o may dugo sa dumi.',
      '⚠ Posibleng food poisoning o impeksiyon. Dili girekomenda ang loperamide kay dili kini angay sa ubang matang sa kalibanga tungod sa impeksiyon. Ang probiotic, kung gitugotan sa pharmacist, dugang nga tabang lang ug dili kapuli sa oral rehydration solution. Gamita ang angay nga ORS ug inom og luwas nga tubig. Pakigkita sa doktor kung molapas sa 2 ka adlaw, adunay taas nga hilanat, o dugo sa tae.'],
    ['ℹ Your headache may be related',
      'Posibleng dulot ng gutom, kakulangan sa tubig, o pagod ang sakit ng ulo. Kumain, uminom ng tubig, at magpahinga muna. Kung nagpapatuloy ang sakit matapos kumain at uminom, maaaring angkop ang iminungkahing gamot.',
      'Posibleng tungod sa kagutom, kakulang sa tubig, o kakapoy ang sakit sa ulo. Kaon, inom og tubig, ug pahuway una. Kung magpadayon ang sakit human mokaon ug moinom, mahimong angay ang gisugyot nga tambal.'],
    ['ℹ You also mentioned a cough.', 'May ubo ka rin. Piliin kung tuyong ubo o may plema upang makapagmungkahi ng gamot.', 'Aduna usab kay ubo. Pilia kung uga o adunay plema aron makasugyot og tambal.'],
    ["Dental symptoms are outside", 'Walang angkop na gamot sa kiosk para sa sakit ng ngipin. Magtanong sa dentista o pharmacist.', 'Walay angay nga tambal sa kiosk para sa sakit sa ngipon. Pangutana sa dentista o pharmacist.'],
    ['We could not confidently identify', 'Hindi namin matukoy ang sintomas. Ilarawan muli ang iyong nararamdaman, tulad ng sakit ng ulo, lagnat, ubo, pagtatae, o sakit ng tiyan.', 'Wala namo matino ang sintomas. Isulti pag-usab ang imong gibati, sama sa sakit sa ulo, hilanat, ubo, kalibanga, o sakit sa tiyan.'],
    ['We found possible symptoms, but not enough', 'Hindi sapat ang impormasyon upang makapagmungkahi ng gamot nang ligtas. Ilarawan muli ang iyong nararamdaman o magtanong sa pharmacist.', 'Dili igo ang impormasyon aron luwas nga makasugyot og tambal. Isulti pag-usab ang imong gibati o pangutana sa pharmacist.'],
    ['Detected condition(s) conflict', 'Maaaring hindi ligtas ang mga gamot sa kiosk para sa iyong kondisyon. Magtanong sa pharmacist.', 'Mahimong dili luwas ang mga tambal sa kiosk para sa imong kondisyon. Pangutana sa pharmacist.'],
  ];
  const products = {
    'Tablet': ['Tablet', 'Tableta', 'Tableta'], 'Chewable Tablet': ['Chewable tablet', 'Ngunguyang tableta', 'Tableta nga usapon'],
    'Capsule': ['Capsule', 'Kapsula', 'Kapsula'], 'Allergy': ['Allergy', 'Allergy', 'Allergy'],
    'Antacid': ['Antacid', 'Para sa asido sa tiyan', 'Para sa aslom nga tiyan'],
    'Pain & Fever': ['Pain & fever', 'Sakit at lagnat', 'Kasakit ug hilanat'],
    'Cold & Flu': ['Cold & flu', 'Sipon at trangkaso', 'Sip-on ug trangkaso'],
    'Cold & Cough': ['Cold & cough', 'Sipon at ubo', 'Sip-on ug ubo'],
    'Cough with Phlegm / Productive Cough': ['Cough with phlegm', 'Ubo na may plema', 'Ubo nga adunay plema'],
    'Cough Suppressant': ['Dry cough', 'Tuyong ubo', 'Uga nga ubo'],
    'Antispasmodic': ['Antispasmodic', 'Para sa paghilab ng tiyan', 'Para sa paghilab sa tiyan'],
    'Anti-diarrhea': ['Anti-diarrhea', 'Para sa pagtatae', 'Para sa kalibanga'],
  };
  const checkout = [
    ['Coins: ₱1, ₱5, ₱10 · Bills: ₱20, ₱50, ₱100', 'Barya: ₱1, ₱5, ₱10 · Papel: ₱20, ₱50, ₱100', 'Sinsilyo: ₱1, ₱5, ₱10 · Papel: ₱20, ₱50, ₱100'],
    ['Product is not available', 'Hindi available ang gamot', 'Dili available ang tambal'],
    ['Out of stock', 'Walang stock', 'Walay stock'],
    ['Not enough available stock', 'Kulang ang available na stock', 'Kulang ang available nga stock'],
    ['Maximum 3 units per medicine', 'Hanggang 3 piraso bawat gamot', 'Hangtod 3 ka piraso matag tambal'],
    ['Maximum 5 different items allowed per purchase', 'Hanggang 5 uri ng gamot bawat pagbili', 'Hangtod 5 ka matang sa tambal matag pagpalit'],
    ['Cash hardware is unhealthy or disconnected', 'Hindi magamit ang tanggapan ng cash. Humingi ng tulong sa staff.', 'Dili magamit ang tigdawat og cash. Pangayo og tabang sa staff.'],
    ['Xendit is not configured', 'Hindi available ang Xendit. Humingi ng tulong sa staff.', 'Dili available ang Xendit. Pangayo og tabang sa staff.'],
    ['Your cart', 'Iyong cart', 'Imong cart'], ['Payment', 'Pagbabayad', 'Pagbayad'],
    ['Your cart is empty. Choose a medicine to begin.', 'Walang laman ang cart. Pumili ng gamot.', 'Walay sulod ang cart. Pilia ang tambal.'],
    ['Total', 'Kabuuan', 'Kinatibuk-an'], ['Maximum 3 units per medicine · 5 different medicines', 'Hanggang 3 piraso bawat gamot · 5 uri ng gamot', 'Hangtod 3 ka piraso matag tambal · 5 ka matang sa tambal'],
    ['Continue shopping', 'Magpatuloy sa pagpili', 'Padayon sa pagpili'], ['Choose payment', 'Pumili ng paraan ng pagbabayad', 'Pilia ang paagi sa pagbayad'],
    ['Close', 'Isara', 'Sirad-i'], ['Back', 'Bumalik', 'Balik'], ['Amount due', 'Halagang babayaran', 'Kantidad nga bayranan'],
    ['Review the total before continuing', 'Suriin ang kabuuan bago magpatuloy', 'Tan-awa ang kinatibuk-an sa dili pa mopadayon'],
    ['Choose a payment method', 'Pumili ng paraan ng pagbabayad', 'Pilia ang paagi sa pagbayad'],
    ['Select how you would like to complete this purchase.', 'Piliin kung paano mo gustong magbayad.', 'Pilia kung unsaon nimo pagbayad.'],
    ['Cash', 'Cash', 'Cash'], ['Cashless', 'Walang cash', 'Walay cash'],
    ['Pay securely through a Xendit invoice', 'Magbayad gamit ang Xendit', 'Pagbayad gamit ang Xendit'],
    ['No change is dispensed', 'Walang ibinibigay na sukli', 'Walay ihatag nga sukli'],
    ['I understand that any overpayment is recorded separately and will not be returned by this machine.', 'Nauunawaan kong itatala ang sobrang bayad at hindi ito ibabalik ng makina.', 'Nasabtan nako nga itala ang sobra nga bayad ug dili kini ibalik sa makina.'],
    ['Starting payment…', 'Sinisimulan ang pagbabayad…', 'Gisugdan ang pagbayad…'],
    ['Continue with cash', 'Magpatuloy gamit ang cash', 'Padayon gamit ang cash'], ['Continue to Xendit', 'Magpatuloy sa Xendit', 'Padayon sa Xendit'],
    ['Insert payment', 'Ipasok ang bayad', 'Isulod ang bayad'],
    ['Please ask for assistance', 'Humingi ng tulong', 'Pangayo og tabang'], ['Payment received', 'Natanggap ang bayad', 'Nadawat ang bayad'],
    ['Please insert the remaining amount', 'Ipasok ang natitirang bayad', 'Isulod ang nahabilin nga bayad'], ['Please insert your money', 'Ipasok ang pera', 'Isulod ang imong kuwarta'],
    ['Payment paused', 'Nakahinto ang pagbabayad', 'Gihunong ang pagbayad'], ['Payment complete', 'Kumpleto ang bayad', 'Kumpleto ang bayad'],
    ['Payment in progress', 'Tumatanggap ng bayad', 'Gidawat ang bayad'], ['Cash acceptor ready', 'Handa nang tumanggap ng pera', 'Andam na modawat og kuwarta'],
    ['Insert ₱1, ₱5, or ₱10 coins and ₱20, ₱50, or ₱100 bills. Your payment is counted automatically.', 'Ipasok ang ₱1, ₱5, o ₱10 na barya at ₱20, ₱50, o ₱100 na papel. Awtomatikong binibilang ang bayad.', 'Isulod ang ₱1, ₱5, o ₱10 nga sinsilyo ug ₱20, ₱50, o ₱100 nga papel. Awtomatikong ihapon ang bayad.'],
    ['Total to pay', 'Kabuuang babayaran', 'Kinatibuk-ang bayranan'], ['Payment progress', 'Progreso ng pagbabayad', 'Progreso sa pagbayad'],
    ['Money inserted', 'Perang naipasok', 'Kuwarta nga nasulod'], ['Amount remaining', 'Natitirang bayad', 'Nahabilin nga bayad'],
    ['Overpayment recorded (no change)', 'Naitalang sobrang bayad (walang sukli)', 'Natala nga sobra nga bayad (walay sukli)'],
    ['This machine does not dispense change. Inserted money is detected and reflected on this screen automatically.', 'Walang ibinibigay na sukli ang makina. Awtomatikong ipinapakita sa screen ang naipasok na pera.', 'Walay ihatag nga sukli ang makina. Awtomatikong ipakita sa screen ang kuwarta nga nasulod.'],
    ['Assistance required:', 'Kailangan ng tulong:', 'Kinahanglan og tabang:'], ['Cancel payment', 'Kanselahin ang pagbabayad', 'Kanselahon ang pagbayad'],
    ['Payment paused — ask for assistance', 'Nakahinto ang pagbabayad — humingi ng tulong', 'Gihunong ang pagbayad — pangayo og tabang'],
    ['Finalizing payment', 'Tinatapos ang pagbabayad', 'Gitapos ang pagbayad'], ['Listening for payment', 'Naghihintay ng bayad', 'Naghulat sa bayad'],
    ['Staff review required', 'Kailangan ng pagsusuri ng staff', 'Kinahanglan susihon sa staff'],
    ['Payment canceled', 'Nakansela ang pagbabayad', 'Nakansela ang pagbayad'], ['Receipt', 'Resibo', 'Resibo'],
    ['Keep this reference for staff', 'Ipakita ang reference na ito sa staff', 'Ipakita kini nga reference sa staff'],
    ['Payment was canceled', 'Nakansela ang pagbabayad', 'Nakansela ang pagbayad'],
    ['Payment successful — stock updated', 'Matagumpay ang pagbabayad — na-update ang stock', 'Malampuson ang pagbayad — na-update ang stock'],
    ['Do not insert money again. Please ask a staff member to review this payment.', 'Huwag nang magpasok ng pera. Hilingin sa staff na suriin ang bayad.', 'Ayaw na pagsulod og kuwarta. Palihug ipasusi sa staff ang bayad.'],
    ['No money was collected and no stock was deducted.', 'Walang nakolektang pera at walang ibinawas sa stock.', 'Walay nadawat nga kuwarta ug walay gibawas sa stock.'],
    ['The sale and inventory deduction are recorded. No medicine motor was activated during this payment-only test.', 'Naitala ang benta at bawas sa stock. Walang pinaandar na motor ng gamot sa pagsubok na ito ng pagbabayad.', 'Natala ang baligya ug bawas sa stock. Walay motor sa tambal nga gipaandar niining pagsulay sa pagbayad.'],
    ['Amount collected', 'Nakolektang halaga', 'Nadawat nga kantidad'], ['Overpayment', 'Sobrang bayad', 'Sobra nga bayad'],
    ['Simulator: no paper receipt was printed.', 'Simulator: walang papel na resibong na-print.', 'Simulator: walay papel nga resibo nga na-print.'],
    ['Please take your printed receipt.', 'Kunin ang na-print na resibo.', 'Kuhaa ang na-print nga resibo.'], ['Printing your receipt…', 'Pini-print ang iyong resibo…', 'Gi-print ang imong resibo…'],
    ['The receipt printer needs attention. Show this screen to staff for your receipt.', 'May problema ang printer. Ipakita ang screen sa staff para sa iyong resibo.', 'Adunay problema ang printer. Ipakita ang screen sa staff para sa imong resibo.'],
    ['Done', 'Tapos na', 'Human na'], ['Order:', 'Order:', 'Order:'], ['· Receipt:', '· Resibo:', '· Resibo:'],
    ['Confirm the no-change policy before starting cash.', 'Kumpirmahin muna ang patakarang walang sukli.', 'Kumpirmaha una ang lagda nga walay sukli.'],
    ['Allow popups to continue to Xendit.', 'Payagan ang popup upang magpatuloy sa Xendit.', 'Tugoti ang popup aron mopadayon sa Xendit.'],
  ];
  const index = language => ({ en: 0, tl: 1, ceb: 2 }[language] ?? 0);
  window.MendoI18n = {
    ui, flags, products, checkout,
    phrase(text, language) {
      const row = checkout.find(row => row.includes(String(text).trim()));
      return row ? String(text).replace(String(text).trim(), row[index(language)]) : text;
    },
    localize(root, language) {
      if (!root) return;
      const nodes = document.createTreeWalker(root, 4); // SHOW_TEXT
      let node;
      while ((node = nodes.nextNode())) {
        // Leave medicine brands, ingredient names, prices and quantities alone.
        node.nodeValue = this.phrase(node.nodeValue, language);
      }
      root.querySelectorAll('[aria-label]').forEach(el => {
        el.setAttribute('aria-label', this.phrase(el.getAttribute('aria-label'), language));
      });
    },
    text(key, language) { return ui[key]?.[index(language)] || key; },
    flag(flag, language) { return flag['message_' + language] || flags[flag.flag]?.[index(language)] || flag.message || ''; },
    notice(text, language) {
      if (language === 'en') return text;
      if (String(text).startsWith('⚠ Condition safety filter')) {
        const brands = String(text).split('Blocked medicine(s): ')[1] || '';
        return ui.conditionSafety[index(language)] + (brands ? ' ' + brands : '');
      }
      const row = notices.find(row => String(text).startsWith(row[0]));
      return row ? row[index(language)] : text;
    },
    product(text, language) {
      // Recommendation categories are normalized to lowercase by the backend.
      const key = Object.keys(products).find(key => key.toLowerCase() === String(text).toLowerCase());
      return key ? products[key][index(language)] : text;
    },
  };
})();
