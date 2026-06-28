package demo;

import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.ItemEvent;
import java.awt.event.ItemListener;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.List;

import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingUtilities;

import com.jnrsmcu.sdk.netdevice.IDataListener;
import com.jnrsmcu.sdk.netdevice.LoginData;
import com.jnrsmcu.sdk.netdevice.NodeData;
import com.jnrsmcu.sdk.netdevice.ParamData;
import com.jnrsmcu.sdk.netdevice.ParamIdsData;
import com.jnrsmcu.sdk.netdevice.ParamItem;
import com.jnrsmcu.sdk.netdevice.RSServer;
import com.jnrsmcu.sdk.netdevice.RealTimeData;
import com.jnrsmcu.sdk.netdevice.StoreData;
import com.jnrsmcu.sdk.netdevice.TelecontrolAck;
import com.jnrsmcu.sdk.netdevice.TimmingAck;
import com.jnrsmcu.sdk.netdevice.TransDataAck;
import com.jnrsmcu.sdk.netdevice.WriteParamAck;

import javax.swing.GroupLayout;
import javax.swing.GroupLayout.Alignment;
import javax.swing.JPanel;
import javax.swing.border.LineBorder;

import java.awt.Color;

import javax.swing.border.TitledBorder;
import javax.swing.LayoutStyle.ComponentPlacement;

public class SwingDemo extends JFrame {

	/**
	 * 
	 */
	private static final long serialVersionUID = -7855826301914463533L;
	private JTextField txtPort;
	private JScrollPane scrollPane;
	private JTextArea textArea;
	private JButton btnStart;
	private JButton btnStop;
	private JCheckBox chkRelay0;
	private JCheckBox chkRelay1;
	private JCheckBox chkRelay2;
	private JCheckBox chkRelay3;
	private JCheckBox chkRelay4;
	private JCheckBox chkRelay5;
	private JCheckBox chkRelay6;
	private JCheckBox chkRelay7;
	private JButton btnTimming;
	private JButton btnCallStore;
	private RSServer rsServer;// ??????????????
	private IDataListener listener = new IDataListener() {

		@Override
		public void receiveTimmingAck(TimmingAck data) {// ??????????
			textArea.append("?????->?????:" + data.getDeviceId() + "\t???????"
					+ data.getStatus() + "\r\n");
		}

		@Override
		public void receiveTelecontrolAck(TelecontrolAck data) {// ???????????
			textArea.append("??????->?????:" + data.getDeviceId() + "\t????????:"
					+ data.getRelayId() + "\t?????:" + data.getStatus() + "\r\n");
		}

		@Override
		public void receiveStoreData(StoreData data) {// ?????????????
			// ???????????????????????????????????????????????????????????????????
			for (NodeData nd : data.getNodeList()) {
				SimpleDateFormat sdf = new SimpleDateFormat("yy-MM-dd HH:mm:ss");
				String str = sdf.format(nd.getRecordTime());

				textArea.append("??????->?????:" + data.getDeviceId() + "\t???:"
						+ nd.getNodeId() + "\t???:" + nd.getTem() + "\t???:"
						+ nd.getHum() + "\t?????:" + str+"\t?????????"+nd.getCoordinateType()+"\t????:"+nd.getLng()+"\t????"+nd.getLat() + "\r\n");

				
				
			}

		}

		@Override
		public void receiveRealtimeData(RealTimeData data) {// ????????????
			// ???????????????????????????????????????????????????????????????????
			for (NodeData nd : data.getNodeList()) {
				textArea.append("??????->?????:" + data.getDeviceId() + "\t???:"
						+ nd.getNodeId() + "\t???:" + nd.getTem() + "\t???:"
						+ nd.getHum() + "\t?????" + data.getLng() + "\t????"
						+ data.getLat() + "\t?????????" + data.getCoordinateType()
						+ "\t???????" + data.getRelayStatus() + "\t???????????"
						+ nd.getFloatValue() + "\t32???????????"
						+ nd.getSignedInt32Value() + "\t32???????????"
						+ nd.getUnSignedInt32Value() + "\r\n");
			}

		}

		@Override
		public void receiveLoginData(LoginData data) {// ?????????????
			textArea.append("???->?????:" + data.getDeviceId() + "\r\n");

		}

		@Override
		public void receiveParamIds(ParamIdsData data) {
			String str = "????????????->??????" + data.getDeviceId() + "\t????????????"
					+ data.getTotalCount() + "\t?????????????" + data.getCount()
					+ "\r\n";
			for (int paramId : data.getPararmIdList())// ???????????id???
			{
				str += paramId + ",";
			}
			textArea.append(str + "\r\n");

		}

		@Override
		public void receiveParam(ParamData data) {
			String str = "??????->??????" + data.getDeviceId() + "\r\n";

			for (ParamItem pararm : data.getParameterList()) {
				str += "????????"
						+ pararm.getParamId()
						+ "\t??????????"
						+ pararm.getDescription()
						+ "\t???????"
						+ (pararm.getValueDescription() == null ? pararm
								.getValue() : pararm.getValueDescription().get(
								pararm.getValue())) + "\r\n";
			}
			textArea.append(str + "\r\n");

		}

		@Override
		public void receiveWriteParamAck(WriteParamAck data) {
			String str = "??????????->??????" + data.getDeviceId() + "\t??????????"
					+ data.getCount() + "\t"
					+ (data.isSuccess() ? "??????" : "???????");
			textArea.append(str + "\r\n");

		}

		@Override
		public void receiveTransDataAck(TransDataAck data) {
			String str = "???????->??????" + data.getDeviceId() + "\t????????"
					+ data.getData() + "\r\n???????" + data.getTransDataLen();
			textArea.append(str + "\r\n");

		}
	};

	private JTextField txtDeviceId;
	private JTextField txtParamIds;
	private JTextField txtParamId;
	private JTextField txtParamVal;
	private JPanel panel_2;
	private JLabel label_4;
	private JTextField txtTransData;
	private JButton btnTrans;

	public SwingDemo() {
		setTitle("Demo");
		setResizable(false);
		setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
		setSize(653, 710);
		setLocationRelativeTo(null);

		JLabel lblNewLabel = new JLabel("\u7AEF\u53E3:");
		lblNewLabel.setBounds(10, 10, 40, 15);

		txtPort = new JTextField();
		txtPort.setBounds(45, 7, 66, 21);
		txtPort.setText("2404");
		txtPort.setColumns(10);

		btnStart = new JButton("\u542F\u52A8");
		btnStart.setBounds(135, 6, 85, 23);
		btnStart.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {

				btnStart.setEnabled(false);
				new Thread(new Runnable() {

					@Override
					public void run() {

						rsServer = RSServer.Initiate(Integer.parseInt(txtPort
								.getText()),"C:/param.dat");// ?????

						rsServer.addDataListener(listener);// ?????????????
						try {
							rsServer.start();
						} catch (InterruptedException e) {
							// TODO Auto-generated catch block
							e.printStackTrace();
						}// ????????????
					}
				}).start();
			}

		});

		btnStop = new JButton("\u505C\u6B62");
		btnStop.setBounds(237, 6, 85, 23);
		btnStop.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {
				btnStart.setEnabled(true);
				rsServer.stop();
			}
		});

		scrollPane = new JScrollPane();
		scrollPane.setBounds(10, 400, 624, 275);

		textArea = new JTextArea();
		scrollPane.setViewportView(textArea);

		JLabel label = new JLabel("\u8BBE\u5907\u5730\u5740:");
		label.setBounds(10, 48, 66, 15);

		txtDeviceId = new JTextField();
		txtDeviceId.setBounds(75, 45, 84, 21);
		txtDeviceId.setText("10000000");
		txtDeviceId.setColumns(10);

		btnTimming = new JButton("\u6821\u65F6");
		btnTimming.setBounds(336, 6, 85, 23);
		btnTimming.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {
				int deviceId = Integer.parseInt(txtDeviceId.getText());
				rsServer.timming(deviceId);
			}
		});

		btnCallStore = new JButton("\u53EC\u5524\u6570\u636E");
		btnCallStore.setBounds(428, 6, 90, 23);
		btnCallStore.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent e) {
				int deviceId = Integer.parseInt(txtDeviceId.getText());

				rsServer.callStoreData(deviceId);
			}
		});

		JPanel panel = new JPanel();
		panel.setBounds(10, 84, 624, 57);
		panel.setBorder(new TitledBorder(null,
				"\u7EE7\u7535\u5668\u63A7\u5236", TitledBorder.LEADING,
				TitledBorder.TOP, null, null));

		JPanel panel_1 = new JPanel();
		panel_1.setBounds(10, 147, 624, 112);
		panel_1.setBorder(new TitledBorder(null, "\u8BBE\u5907\u53C2\u6570",
				TitledBorder.LEADING, TitledBorder.TOP, null, null));

		panel_2 = new JPanel();
		panel_2.setBounds(10, 269, 624, 113);
		panel_2.setBorder(new TitledBorder(null, "\u6570\u636E\u900F\u4F20",
				TitledBorder.LEADING, TitledBorder.TOP, null, null));
		panel_2.setLayout(null);

		label_4 = new JLabel(
				"\u900F\u4F20\u6570\u636E\uFF0C16\u8FDB\u5236\u5B57\u7B26\u4E32");
		label_4.setBounds(10, 23, 419, 15);
		panel_2.add(label_4);

		txtTransData = new JTextField();
		txtTransData.setBounds(10, 48, 604, 21);
		panel_2.add(txtTransData);
		txtTransData.setColumns(10);

		btnTrans = new JButton("\u6570\u636E\u900F\u4F20");
		btnTrans.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {
				int deviceId = Integer.parseInt(txtDeviceId.getText());

				rsServer.trans(deviceId, txtTransData.getText());
			}
		});
		btnTrans.setBounds(10, 79, 93, 23);
		panel_2.add(btnTrans);
		panel_1.setLayout(null);

		JLabel label_1 = new JLabel(
				"\u53C2\u6570\u7F16\u53F7\uFF0C\u7528\u4E8E\u8BFB\u53D6\u8BBE\u5907\u53C2\u6570\uFF08\u591A\u4E2A\u7F16\u53F7\u7528\u82F1\u6587,\u5206\u9694\uFF09");
		label_1.setBounds(10, 22, 421, 15);
		panel_1.add(label_1);

		txtParamIds = new JTextField();
		txtParamIds.setText("1,2,3,4,5,6,7,8,9,10");
		txtParamIds.setBounds(10, 47, 421, 21);
		panel_1.add(txtParamIds);
		txtParamIds.setColumns(10);

		JLabel label_2 = new JLabel("\u53C2\u6570\u7F16\u53F7");
		label_2.setBounds(10, 78, 54, 15);
		panel_1.add(label_2);

		txtParamId = new JTextField();
		txtParamId.setBounds(68, 75, 66, 21);
		panel_1.add(txtParamId);
		txtParamId.setColumns(10);

		JLabel label_3 = new JLabel("\u53C2\u6570\u503C");
		label_3.setBounds(144, 78, 54, 15);
		panel_1.add(label_3);

		txtParamVal = new JTextField();
		txtParamVal.setBounds(202, 75, 66, 21);
		panel_1.add(txtParamVal);
		txtParamVal.setColumns(10);

		JButton btnReadParametersList = new JButton(
				"\u8BFB\u53D6\u8BBE\u5907\u53C2\u6570\u5217\u8868");
		btnReadParametersList.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {
				int deviceId = Integer.parseInt(txtDeviceId.getText());
				rsServer.callParamList(deviceId);// ???????????????????
			}
		});
		btnReadParametersList.setBounds(460, 18, 142, 23);
		panel_1.add(btnReadParametersList);

		JButton btnReadParameters = new JButton(
				"\u8BFB\u53D6\u8BBE\u5907\u53C2\u6570");
		btnReadParameters.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {
				int deviceId = Integer.parseInt(txtDeviceId.getText());
				List<Integer> ids = new ArrayList<Integer>();
				String[] idArray = txtParamIds.getText().split(",");
				for (String str : idArray) {
					try {
						ids.add(Integer.parseInt(str));
					} catch (Exception e) {
					}
				}
				if (ids.size() >= 115) {

					JOptionPane.showMessageDialog(null, "????????????????????115??",
							"???", JOptionPane.INFORMATION_MESSAGE);
					return;
				}
				rsServer.callParam(deviceId, ids);

			}
		});
		btnReadParameters.setBounds(460, 46, 142, 23);
		panel_1.add(btnReadParameters);

		JButton btnWriteParameters = new JButton(
				"\u4E0B\u8F7D\u8BBE\u5907\u53C2\u6570");
		btnWriteParameters.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent arg0) {

				int deviceId = Integer.parseInt(txtDeviceId.getText());
				List<ParamItem> parameters = new ArrayList<ParamItem>();

				try {

					parameters.add(ParamItem.New(
							Integer.parseInt(txtParamId.getText()),
							txtParamVal.getText()));
				} catch (Exception ex) {
					JOptionPane.showMessageDialog(null, ex.getMessage(), "???",
							JOptionPane.INFORMATION_MESSAGE);
					return;
				}
				if (parameters.size() > 115) {

					JOptionPane.showMessageDialog(null, "???????????????????????115??",
							"???", JOptionPane.INFORMATION_MESSAGE);
					return;
				}
				rsServer.writeParam(deviceId, parameters);
			}
		});
		btnWriteParameters.setBounds(460, 74, 142, 23);
		panel_1.add(btnWriteParameters);

		chkRelay0 = new JCheckBox("\u7EE7\u7535\u56680");
		panel.add(chkRelay0);

		chkRelay1 = new JCheckBox("\u7EE7\u7535\u56681");
		panel.add(chkRelay1);

		chkRelay2 = new JCheckBox("\u7EE7\u7535\u56682");
		panel.add(chkRelay2);

		chkRelay3 = new JCheckBox("\u7EE7\u7535\u56683");
		panel.add(chkRelay3);

		chkRelay4 = new JCheckBox("\u7EE7\u7535\u56684");
		panel.add(chkRelay4);

		chkRelay5 = new JCheckBox("\u7EE7\u7535\u56685");
		panel.add(chkRelay5);

		chkRelay6 = new JCheckBox("\u7EE7\u7535\u56686");
		panel.add(chkRelay6);

		chkRelay7 = new JCheckBox("\u7EE7\u7535\u56687");
		panel.add(chkRelay7);
		chkRelay7.addItemListener(new ChkItemListener(7));
		chkRelay6.addItemListener(new ChkItemListener(6));
		chkRelay5.addItemListener(new ChkItemListener(5));
		chkRelay4.addItemListener(new ChkItemListener(4));
		chkRelay3.addItemListener(new ChkItemListener(3));
		chkRelay2.addItemListener(new ChkItemListener(2));
		chkRelay1.addItemListener(new ChkItemListener(1));
		chkRelay0.addItemListener(new ChkItemListener(0));
		getContentPane().setLayout(null);
		getContentPane().add(txtPort);
		getContentPane().add(lblNewLabel);
		getContentPane().add(btnStart);
		getContentPane().add(btnStop);
		getContentPane().add(btnTimming);
		getContentPane().add(btnCallStore);
		getContentPane().add(txtDeviceId);
		getContentPane().add(label);
		getContentPane().add(panel_1);
		getContentPane().add(panel);
		getContentPane().add(panel_2);
		getContentPane().add(scrollPane);
	}

	class ChkItemListener implements ItemListener {

		private int relayId = 0;

		public ChkItemListener(int relayId) {
			this.relayId = relayId;
		}

		@Override
		public void itemStateChanged(ItemEvent e) {
			JCheckBox jcb = (JCheckBox) e.getItem();
			int deviceId = Integer.parseInt(txtDeviceId.getText());
			if (jcb.isSelected()) {

				try {
					rsServer.telecontrol(deviceId, relayId, 0, 0);
				} catch (Exception e1) {
					e1.printStackTrace();
				}

			} else {
				try {
					rsServer.telecontrol(deviceId, relayId, 1, 0);
				} catch (Exception e1) {
					e1.printStackTrace();
				}
			}
		}
	}

	public static void main(String[] args) {
		new SwingDemo().setVisible(true);

	}
}
