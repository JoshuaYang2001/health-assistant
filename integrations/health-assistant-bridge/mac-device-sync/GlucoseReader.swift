import CoreBluetooth
import Foundation

final class Reader: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    private var central: CBCentralManager!
    private var meter: CBPeripheral?
    private var measurement: CBCharacteristic?
    private var control: CBCharacteristic?
    private var enabled = Set<CBUUID>()
    private var required = Set<CBUUID>()
    private var packets: [String] = []
    private var contextPackets: [String] = []
    private var timer: DispatchWorkItem?
    private var finished = false
    private let glucoseService = CBUUID(string: "1808")
    private let glucoseMeasurement = CBUUID(string: "2A18")
    private let recordControl = CBUUID(string: "2A52")
    private let glucoseContext = CBUUID(string: "2A34")
    private let nameFilter: String

    init(nameFilter: String) {
        self.nameFilter = nameFilter.lowercased()
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
        scheduleTimeout(45, "Timed out waiting for the meter. Put it into Bluetooth pairing mode and try again.")
    }

    private func scheduleTimeout(_ seconds: Double, _ message: String) {
        timer?.cancel()
        let next = DispatchWorkItem { [weak self] in self?.fail(message) }
        timer = next
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: next)
    }

    private func fail(_ message: String) {
        guard !finished else { return }
        finished = true
        timer?.cancel()
        central.stopScan()
        if let meter { central.cancelPeripheralConnection(meter) }
        FileHandle.standardError.write(Data((message + "\n").utf8))
        exit(1)
    }

    private func succeed() {
        guard !finished, let meter else { return }
        finished = true
        timer?.cancel()
        central.stopScan()
        let body: [String: Any] = ["device_id": meter.identifier.uuidString, "packets": packets, "context_packets": contextPackets]
        do {
            let encoded = try JSONSerialization.data(withJSONObject: body, options: [.sortedKeys])
            FileHandle.standardOutput.write(encoded)
            FileHandle.standardOutput.write(Data("\n".utf8))
            central.cancelPeripheralConnection(meter)
            exit(0)
        } catch {
            FileHandle.standardError.write(Data("Could not encode meter data.\n".utf8))
            exit(1)
        }
    }

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            central.scanForPeripherals(withServices: nil, options: nil)
        case .poweredOff: fail("Bluetooth is off on this Mac.")
        case .unauthorized: fail("Bluetooth access was denied. Allow Bluetooth for this application in macOS settings.")
        case .unsupported: fail("Bluetooth Low Energy is unavailable on this Mac.")
        default: break
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        guard meter == nil else { return }
        let name = (peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? "").lowercased()
        guard name.contains(nameFilter) else { return }
        meter = peripheral
        meter?.delegate = self
        central.stopScan()
        central.connect(peripheral, options: nil)
        scheduleTimeout(40, "Meter connection timed out. Complete the macOS Bluetooth pairing prompt if shown.")
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        peripheral.discoverServices([glucoseService])
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        fail("Could not connect to the meter. Check pairing and try again.")
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        fail("The meter disconnected before reporting a complete transfer; nothing was imported.")
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil, let service = peripheral.services?.first(where: { $0.uuid == glucoseService }) else {
            fail("The meter did not expose the Bluetooth Glucose Service.")
            return
        }
        peripheral.discoverCharacteristics([glucoseMeasurement, glucoseContext, recordControl], for: service)
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil, let characteristics = service.characteristics else {
            fail("Could not read meter services. Check the Bluetooth pairing prompt.")
            return
        }
        measurement = characteristics.first(where: { $0.uuid == glucoseMeasurement })
        control = characteristics.first(where: { $0.uuid == recordControl })
        guard let measurement, let control else {
            fail("The meter did not expose the required glucose history characteristics.")
            return
        }
        required = [glucoseMeasurement, recordControl]
        if let context = characteristics.first(where: { $0.uuid == glucoseContext }) {
            required.insert(glucoseContext)
            peripheral.setNotifyValue(true, for: context)
        }
        peripheral.setNotifyValue(true, for: measurement)
        peripheral.setNotifyValue(true, for: control)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, characteristic.isNotifying else {
            fail("Meter notifications could not be enabled. Complete Bluetooth pairing and try again.")
            return
        }
        enabled.insert(characteristic.uuid)
        if enabled == required, let control {
            enabled.removeAll()
            required.removeAll()
            peripheral.writeValue(Data([0x01, 0x01]), for: control, type: .withResponse)
            scheduleTimeout(60, "The meter did not finish sending its records; nothing was imported.")
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if error != nil { fail("The meter rejected the history request.") }
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil, let value = characteristic.value else {
            fail("The meter returned an incomplete transfer; nothing was imported.")
            return
        }
        if characteristic.uuid == glucoseMeasurement {
            guard packets.count < 5000 else { fail("The meter returned too many records."); return }
            packets.append(value.map { String(format: "%02x", $0) }.joined())
        } else if characteristic.uuid == glucoseContext {
            guard contextPackets.count < 5000 else { fail("The meter returned too many context records."); return }
            contextPackets.append(value.map { String(format: "%02x", $0) }.joined())
        } else if characteristic.uuid == recordControl {
            let data = [UInt8](value)
            guard data.count == 4, data[0] == 0x06, data[1] == 0x00, data[2] == 0x01 else {
                fail("The meter returned an unrecognized history response.")
                return
            }
            if data[3] == 0x01 || data[3] == 0x06 { succeed() }
            else { fail("The meter reported that the history transfer failed.") }
        }
    }
}

let args = CommandLine.arguments
let filter = args.count > 1 ? args[1] : "accu-chek"
guard !filter.isEmpty else {
    FileHandle.standardError.write(Data("A meter name filter is required.\n".utf8))
    exit(1)
}
let reader = Reader(nameFilter: filter)
RunLoop.main.run()
